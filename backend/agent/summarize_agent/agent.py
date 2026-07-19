import asyncio
import os

from langchain.agents import create_agent
from langchain.tools import tool, ToolRuntime
from langchain_core.messages import HumanMessage

from ..context import AgentContext
from ..mcp_client import get_mcp_tools


SUMMARIZE_SYSTEM_PROMPT = (
    "You are a specialist summarizer agent for an issue-tracking system. "
    "Given a query about a specific issue, first identify which issue is "
    "being asked about, then call the retrieve_issue_updates tool exactly "
    "once to fetch that issue's current details plus its full update "
    "history (returned newest-first).\n\n"
    "From the tool result, produce a single, concise natural-language "
    "summary that covers:\n"
    "1. The issue's current status — its state (e.g. open/in-progress/"
    "resolved/closed) and any other current-state fields returned.\n"
    "2. A synthesis, not a raw list, of all the updates in its history: "
    "what happened, in what order, and how the situation evolved — call "
    "out key turning points rather than restating every field.\n\n"
    "If the tool returns null/no result (the issue does not exist, or the "
    "caller does not have access to it), say so plainly and do not "
    "fabricate a status or update history — never guess at an issue's "
    "state when no data was returned."
)


async def _get_summarizer_tools():
    mcp_tools = await get_mcp_tools()
    retrieve_issue_updates_tool = next(
        (t for t in mcp_tools if t.name == "retrieve_issue_updates"), None
    )
    if retrieve_issue_updates_tool is None:
        raise RuntimeError(
            "retrieve_issue_updates tool not found among MCP server tools — "
            "is the MCP server (Phase 4.7) reachable and up to date?"
        )
    return [retrieve_issue_updates_tool]


_summarizer_agent = None
_summarizer_agent_lock = asyncio.Lock()


async def get_summarizer_agent():
    """
    Builds the summarizer sub-agent with just the retrieve_issue_updates
    tool on first use and caches it, guarded by a lock so concurrent callers
    can't race and build it more than once (mirrors core.py's get_agent()).
    """
    global _summarizer_agent
    if _summarizer_agent is None:
        async with _summarizer_agent_lock:
            if _summarizer_agent is None:
                tools = await _get_summarizer_tools()
                _summarizer_agent = create_agent(
                    model=os.getenv("SUMMARIZE_AGENT_MODEL", "openai:gpt-5-mini"),
                    tools=tools,
                    system_prompt=SUMMARIZE_SYSTEM_PROMPT,
                    context_schema=AgentContext,
                    name="summarize_agent",
                )
    return _summarizer_agent


@tool
async def consult_summarizer_agent(runtime: ToolRuntime[AgentContext], query: str) -> str:
    """Delegate an issue-summary question — current status plus a synthesis
    of all updates/history for a specific issue — to the specialist
    summarizer sub-agent, which calls retrieve_issue_updates and writes the
    summary. Do not use this for customer/account/CRM profile questions —
    use consult_customer_profile_agent for those."""
    agent = await get_summarizer_agent()
    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=query)]},
        context=runtime.context,
    )
    return result["messages"][-1].content
