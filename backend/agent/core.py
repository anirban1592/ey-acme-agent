import asyncio
import os

from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest, dynamic_prompt
from langchain_core.messages import HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.interceptors import MCPToolCallRequest
from langchain_openai import ChatOpenAI

from models import User

from .context import AgentContext

# Initialize the OpenAI model
# It uses the OPENAI_API_KEY environment variable by default
api_key = os.getenv("OPENAI_API_KEY") or "mock-key"

# Create the ChatOpenAI model
model = ChatOpenAI(
    model=os.getenv("OPENAI_MODEL_NAME", "gpt-5.1"),
    temperature=0.0,
    openai_api_key=api_key
)

BASE_SYSTEM_PROMPT = "You are a helpful agent. Your job is to process user queries. You are looking after a database with the help of tools, agents, sub-agents, and workflows, but right now you have access to a bunch of tools which you can use to query the database of all the issues. Whenever a user asks a particular query, decide if you want to use a particular tool and execute the tool, and then curate the final response. "


@dynamic_prompt
def role_aware_prompt(request: ModelRequest) -> str:
    ctx: AgentContext = request.runtime.context
    return (
        f"{BASE_SYSTEM_PROMPT}\n\n"
        f"You are assisting the logged-in user '{ctx.username}', whose roles "
        f"are {ctx.roles}. Data access is enforced server-side on every tool "
        f"call regardless of what role you ask for — do not claim or imply "
        f"access to data beyond what tool results actually return."
    )


async def inject_role_interceptor(request: MCPToolCallRequest, handler):
    """Overwrites the 'roles' tool-call argument with the authenticated
    caller's actual roles, taken from the per-invocation AgentContext —
    never from whatever the LLM put in its tool call. This is the real
    RBAC enforcement point; role_aware_prompt above is only a convenience
    for the model, not a security boundary.
    """
    if request.name == "retrieve_customer_profile":
        ctx: AgentContext = request.runtime.context
        request = request.override(args={**request.args, "roles": list(ctx.roles)})
    return await handler(request)


async def get_mcp_tools():
    """
    Initializes the MultiServerMCPClient and retrieves the tools from the MCP server.
    """
    client = MultiServerMCPClient(
        {
            "issues": {
                "transport": "http",
                "url": os.getenv("MCP_SERVER_URL", "http://mcp:9000/mcp"),
            }
        },
        tool_interceptors=[inject_role_interceptor],
    )
    tools = await client.get_tools()
    return tools


_agent = None
_agent_lock = asyncio.Lock()


async def get_agent():
    """
    Builds the LangChain agent with MCP tools on first use and caches it.
    Guarded by a lock so concurrent callers (e.g. multiple WebSocket
    connections) can't race and build it more than once. context_schema lets
    each ainvoke() call supply its own AgentContext without rebuilding the
    agent, so this singleton stays safe to share across users/requests.
    """
    global _agent
    if _agent is None:
        async with _agent_lock:
            if _agent is None:
                tools = await get_mcp_tools()
                _agent = create_agent(
                    model=model,
                    tools=tools,
                    middleware=[role_aware_prompt],
                    context_schema=AgentContext,
                )
    return _agent


async def respond(message: str, user: User) -> str:
    """
    Invokes the LangChain agent with the user message, scoped to the
    authenticated caller via AgentContext, and returns the final AI reply.
    """
    agent = await get_agent()
    input_data = {"messages": [HumanMessage(content=message)]}
    context = AgentContext(username=user.username, roles=user.roles)
    result = await agent.ainvoke(input_data, context=context)

    messages = result.get("messages", [])
    if messages:
        return messages[-1].content
    return "No response generated."
