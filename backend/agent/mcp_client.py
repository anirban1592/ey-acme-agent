import os

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.interceptors import MCPToolCallRequest

from .context import AgentContext


async def inject_role_interceptor(request: MCPToolCallRequest, handler):
    """Overwrites the 'roles' tool-call argument with the authenticated
    caller's actual roles, taken from the per-invocation AgentContext —
    never from whatever the LLM put in its tool call. Lives here (not in
    core.py) so every agent graph that talks to the MCP server shares this
    exact same RBAC enforcement point, rather than each duplicating it.
    """
    if request.name in ("retrieve_customer_profile", "retrieve_issue_updates"):
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
