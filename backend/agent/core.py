import asyncio
import os

from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest, dynamic_prompt
from langchain_core.messages import HumanMessage

from models import User

from .checkpointer import get_checkpointer
from .context import AgentContext
from .customer_profile import consult_customer_profile_agent
from .escalation_agent import consult_escalation_agent
from .mcp_client import get_mcp_tools
from .summarize_agent import consult_summarizer_agent


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
                tools = (await get_mcp_tools()) + [
                    consult_customer_profile_agent,
                    consult_summarizer_agent,
                    consult_escalation_agent,
                ]
                checkpointer = await get_checkpointer()
                _agent = create_agent(
                    model=os.getenv("MAIN_AGENT_MODEL", "openai:gpt-5.1"),
                    tools=tools,
                    middleware=[role_aware_prompt],
                    context_schema=AgentContext,
                    checkpointer=checkpointer,
                )
    return _agent


async def respond(message: str, user: User, thread_id: str) -> str:
    """
    Invokes the LangChain agent with the user message, scoped to the
    authenticated caller via AgentContext, and persisted/resumed via the
    Redis checkpointer keyed on thread_id. Returns the final AI reply.
    """
    agent = await get_agent()
    input_data = {"messages": [HumanMessage(content=message)]}
    context = AgentContext(username=user.username, roles=user.roles)
    config = {"configurable": {"thread_id": thread_id}}
    result = await agent.ainvoke(input_data, context=context, config=config)

    messages = result.get("messages", [])
    if messages:
        return messages[-1].content
    return "No response generated."
