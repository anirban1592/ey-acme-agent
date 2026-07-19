import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import Union

from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest, dynamic_prompt
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import HumanMessage

from models import User

from .checkpointer import get_checkpointer
from .context import AgentContext
from .customer_profile import consult_customer_profile_agent
from .escalation_agent import consult_escalation_agent
from .mcp_client import get_mcp_tools
from .response_types import (
    CONTENT_TO_RESPONSE,
    DUMMY_RECIPIENT_EMAIL,
    BulletSummaryContent,
    ChatMessageContent,
    CustomerProfileContent,
    ErrorResponse,
    EscalationEmailDraft,
    EscalationEmailResponse,
    IssueListContent,
    WsResponse,
    resolve_role_context,
)
from .summarize_agent import consult_summarizer_agent


BASE_SYSTEM_PROMPT = (
    "You are a helpful agent. Your job is to process user queries. You are "
    "looking after a database with the help of tools, agents, sub-agents, "
    "and workflows, but right now you have access to a bunch of tools which "
    "you can use to query the database of all the issues. Whenever a user "
    "asks a particular query, decide if you want to use a particular tool "
    "and execute the tool, then produce your final answer in whichever "
    "structured shape actually fits it: a list of issues, a customer "
    "profile, an escalation email draft, a bullet-point summary, or — for "
    "plain conversation that isn't any of those — a chat message. Base "
    "structured fields on what the tools actually returned; never fabricate "
    "values that no tool result supports. When using the chat message shape, "
    "its text is the literal reply shown directly to the user, verbatim — "
    "never a description of your plan, reasoning, or what you intend to say.\n\n"
    "If you called a tool that returned structured data — a list of issues, "
    "a customer profile, or an issue's history/updates/timeline — always "
    "answer using the matching structured shape (issue_list, "
    "customer_profile, or bullet_summary respectively), never chat_message. "
    "For issue history specifically, use bullet_summary with heading = the "
    "issue's current status and points = the update timeline, regardless of "
    "whether you called retrieve_issue_updates directly or via "
    "consult_summarizer_agent. chat_message is reserved for genuinely "
    "tool-free, plain conversation."
)


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
                    response_format=ToolStrategy(
                        Union[
                            IssueListContent,
                            CustomerProfileContent,
                            EscalationEmailDraft,
                            BulletSummaryContent,
                            ChatMessageContent,
                        ]
                    ),
                )
    return _agent


async def respond(message: str, user: User, thread_id: str) -> WsResponse:
    """
    Invokes the LangChain agent with the user message, scoped to the
    authenticated caller via AgentContext, and persisted/resumed via the
    Redis checkpointer keyed on thread_id. Returns a typed, enveloped
    response (see response_types.py) — never raw text. Envelope fields
    (request_id/timestamp/role_context) are always supplied here, never
    trusted from the LLM's own structured output, mirroring the RBAC
    convention of never trusting the model for security/consistency-critical
    fields.
    """
    envelope = dict(
        request_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc),
        role_context=resolve_role_context(user.roles),
    )
    try:
        agent = await get_agent()
        input_data = {"messages": [HumanMessage(content=message)]}
        context = AgentContext(username=user.username, roles=user.roles)
        config = {"configurable": {"thread_id": thread_id}}
        result = await agent.ainvoke(input_data, context=context, config=config)

        content = result.get("structured_response")
        if type(content) is EscalationEmailDraft:
            # `to` is never LLM-controlled, even at this outer layer — always
            # the shared placeholder, attached here in Python, not copied
            # from whatever the model produced.
            return EscalationEmailResponse(to=DUMMY_RECIPIENT_EMAIL, **content.model_dump(), **envelope)
        response_cls = CONTENT_TO_RESPONSE.get(type(content))
        if response_cls is None:
            raise ValueError(f"Unrecognized structured_response type: {type(content)!r}")
        return response_cls(**content.model_dump(), **envelope)
    except Exception as e:
        return ErrorResponse(message=str(e), code="agent_error", **envelope)
