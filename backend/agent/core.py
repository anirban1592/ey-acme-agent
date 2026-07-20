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
from .customer_profile import get_customer_profile
from .escalation_agent import consult_escalation_agent
from .guardrail import PromptInjectionGuardrailMiddleware
from .mcp_client import get_mcp_tools
from .response_types import (
    BulletSummaryContent,
    ChatMessageContent,
    ChatMessageResponse,
    CompositeContent,
    CustomerProfileContent,
    ErrorResponse,
    EscalationEmailDraft,
    IssueListContent,
    WsResponse,
    build_ws_response,
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
    "If the user is asking to see/view/list an entity itself — the issues "
    "for a customer, a customer's profile, an issue's history/updates/"
    "timeline — always answer using the matching structured shape "
    "(issue_list, customer_profile, or bullet_summary respectively) once "
    "you've called the tool that returns it, never chat_message. For issue "
    "history specifically, use bullet_summary with heading = the issue's "
    "current status and points = the update timeline, regardless of whether "
    "you called retrieve_issue_updates directly or via "
    "consult_summarizer_agent.\n\n"
    "That structured-shape rule is for requests to see the whole entity. A "
    "narrower follow-up question that only asks about one fact within an "
    "entity — e.g. \"how many employees does it have\", \"who are the "
    "primary contacts\", \"what's the account tier\" — must be answered with "
    "chat_message containing just the direct answer (a word or short "
    "phrase), never by re-emitting the full customer_profile/issue_list/"
    "bullet_summary shape again. Before calling any tool, check whether the "
    "conversation so far already contains the data needed to answer — e.g. "
    "a customer profile or issue list you already fetched earlier in this "
    "same conversation — and if so, answer directly from that instead of "
    "calling the tool again. chat_message is otherwise reserved for "
    "genuinely tool-free, plain conversation.\n\n"
    "A single user message can ask for more than one thing. If answering it "
    "fully needs more than one of the shapes above, you MUST call the "
    "CompositeContent tool with one block per shape — never answer with only "
    "one shape and silently drop the rest of the question, and never call "
    "more than one of the other structured-output tools in the same turn "
    "(e.g. calling both CustomerProfileContent and IssueListContent directly "
    "is invalid; CompositeContent with two blocks is the only valid way to "
    "combine them). For example: \"Show me the company profile for Google "
    "and list its issues\" requires calling both a profile tool and an "
    "issues tool, then responding with CompositeContent containing one "
    "CustomerProfileContent block AND one IssueListContent block — "
    "responding with CustomerProfileContent alone is wrong even though it is "
    "part of a correct answer. Never use CompositeContent to wrap what is "
    "really a single-shape answer, and never fabricate a block with no "
    "supporting tool result."
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
                    get_customer_profile,
                    consult_summarizer_agent,
                    consult_escalation_agent,
                ]
                checkpointer = await get_checkpointer()
                _agent = create_agent(
                    model=os.getenv("MAIN_AGENT_MODEL", "openai:gpt-5.1"),
                    tools=tools,
                    middleware=[PromptInjectionGuardrailMiddleware(), role_aware_prompt],
                    context_schema=AgentContext,
                    checkpointer=checkpointer,
                    response_format=ToolStrategy(
                        Union[
                            IssueListContent,
                            CustomerProfileContent,
                            EscalationEmailDraft,
                            BulletSummaryContent,
                            ChatMessageContent,
                            CompositeContent,
                        ]
                    ),
                )
    return _agent


async def respond(message: str, user: User, thread_id: str) -> list[WsResponse]:
    """
    Invokes the LangChain agent with the user message, scoped to the
    authenticated caller via AgentContext, and persisted/resumed via the
    Redis checkpointer keyed on thread_id. Returns a list of typed, enveloped
    responses (see response_types.py) — never raw text — one per WebSocket
    message the caller should send. Normally a single-element list; more than
    one only when the agent used the composite/blocks shape for a turn that
    genuinely spanned multiple structured shapes. Envelope fields
    (request_id/timestamp/role_context) are always supplied here, never
    trusted from the LLM's own structured output, mirroring the RBAC
    convention of never trusting the model for security/consistency-critical
    fields.
    """
    role_context = resolve_role_context(user.roles)

    def fresh_envelope() -> dict:
        return dict(request_id=str(uuid.uuid4()), timestamp=datetime.now(timezone.utc), role_context=role_context)

    try:
        agent = await get_agent()
        input_data = {"messages": [HumanMessage(content=message)]}
        context = AgentContext(username=user.username, roles=user.roles)
        config = {"configurable": {"thread_id": thread_id}}
        result = await agent.ainvoke(input_data, context=context, config=config)

        content = result.get("structured_response")
        if content is None:
            # Every normal completion is required to end in a
            # structured_response (response_format=ToolStrategy(...)); None
            # here unambiguously means a before_agent/before_model guardrail
            # short-circuited via jump_to="end" before the model could run.
            return [ChatMessageResponse(message=result["messages"][-1].content, **fresh_envelope())]
        if type(content) is CompositeContent:
            if not content.blocks:
                raise ValueError("CompositeContent returned with no blocks")
            return [build_ws_response(block, fresh_envelope()) for block in content.blocks]
        return [build_ws_response(content, fresh_envelope())]
    except Exception as e:
        return [ErrorResponse(message=str(e), code="agent_error", **fresh_envelope())]
