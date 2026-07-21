"""
Runs the real production agent (the same singleton backend/agent/core.py's
respond() uses) for one eval question, capturing both the final reply text
and every top-level tool call the main agent made — data respond() itself
never exposes, since its contract to WebSocket callers is just
`list[WsResponse]`.

This intentionally mirrors respond()'s own invocation of agent.ainvoke()
(context, config, HumanMessage) rather than calling respond() directly, so
that a ToolCallRecorder callback can also be threaded through — respond()
has no callbacks parameter, and adding tool-call introspection there for
production traffic isn't warranted just to serve evals. Keep this in sync
with backend/agent/core.py's respond() if its invocation shape changes.
"""

import asyncio
import sys
import uuid
from pathlib import Path

# backend/ needs to be on sys.path for flat imports used throughout the
# agent package (e.g. `from models import User`), matching how the real
# server runs (Dockerfile's WORKDIR is backend/ itself, with no `backend`
# package in scope there).
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from agent.context import AgentContext  # noqa: E402
from agent.core import get_agent  # noqa: E402
from agent.response_types import CompositeContent  # noqa: E402
from deepeval.dataset import EvaluationDataset  # noqa: E402
from deepeval.test_case import LLMTestCase, ToolCall  # noqa: E402
from langchain_core.callbacks import BaseCallbackHandler  # noqa: E402
from langchain_core.messages import HumanMessage  # noqa: E402
from models import User  # noqa: E402

# Mirrors postgres/initv2.sql's seed users/roles exactly (alice=admin,
# bob=sales, charlie=operations, tony=support, eve=no role). id/email values
# are arbitrary — respond()/AgentContext only ever read username and roles.
SEED_USERS: dict[str, User] = {
    "alice": User(id=1, username="alice", email="alice@example.com", keycloak_id=None, roles=["admin"]),
    "bob": User(id=2, username="bob", email="bob@example.com", keycloak_id=None, roles=["sales"]),
    "charlie": User(id=3, username="charlie", email="charlie@example.com", keycloak_id=None, roles=["operations"]),
    "tony": User(id=4, username="tony", email="tony@example.com", keycloak_id=None, roles=["support"]),
    "eve": User(id=5, username="eve", email="eve@example.com", keycloak_id=None, roles=[]),
}


class ToolCallRecorder(BaseCallbackHandler):
    """Records every tool the agent graph invokes, in call order.

    Runs inline (not dispatched to a thread executor) since appending to a
    list needs no real async work — avoids executor overhead/warnings for a
    callback this lightweight.
    """

    run_inline = True

    def __init__(self):
        self.tool_calls: list[ToolCall] = []

    def on_tool_start(self, serialized, input_str, **kwargs):
        name = (serialized or {}).get("name") or kwargs.get("name") or "unknown_tool"
        self.tool_calls.append(ToolCall(name=name))


def _render_content(content) -> str:
    """Renders a structured_response content model into the kind of
    human-readable text a user would actually see (mirrors what the
    frontend's typed renderers show), so the GEval judge sees legible text
    instead of raw JSON."""
    type_name = type(content).__name__

    if type_name == "IssueListContent":
        if not content.issues:
            return f"No issues found for {content.customer_name}."
        lines = [f"Issues for {content.customer_name}:"]
        lines += [f"- [{i.id}] {i.title} ({i.status}), updated {i.updated_at}" for i in content.issues]
        return "\n".join(lines)

    if type_name == "CustomerProfileContent":
        if not content.fields:
            return f"No profile found for {content.customer_name}."
        lines = [f"Customer profile for {content.customer_name}:"]
        lines += [f"- {k}: {v}" for k, v in content.fields.items()]
        return "\n".join(lines)

    if type_name in ("EscalationEmailDraft", "EscalationEmailContent"):
        to = getattr(content, "to", None)
        header = f"To: {to}\n" if to else ""
        return f"{header}Subject: {content.subject}\n\n{content.body}"

    if type_name == "BulletSummaryContent":
        return "\n".join([content.heading] + [f"- {p}" for p in content.points])

    if type_name == "ChatMessageContent":
        return content.message

    return content.model_dump_json()


# One full agent turn can involve several chained LLM calls (guardrail
# classifier, main agent, a sub-agent's own model call, structured-output
# finalization), so a modest-tier OpenAI org's TPM budget can be exhausted
# well before 19 sequential goldens finish. Retry on 429s with backoff
# rather than fail the whole run on a transient rate limit. A tight org-wide
# TPM ceiling (e.g. a 200k/min Tier-1 limit) can stay saturated for minutes
# at a time, not just one refill cycle, so this retries persistently with a
# capped backoff rather than giving up after a handful of short waits.
_MAX_RATE_LIMIT_RETRIES = 12
_RATE_LIMIT_BACKOFF_SECONDS = 30
_RATE_LIMIT_MAX_BACKOFF_SECONDS = 90


async def run_case(question: str, username: str) -> tuple[str, list[ToolCall]]:
    """Invokes the real singleton agent as the given seeded user and returns
    (actual_output_text, tools_called). Each call uses a fresh thread_id so
    golden cases never share Redis-checkpointed conversation state."""
    user = SEED_USERS[username]
    recorder = ToolCallRecorder()

    agent = await get_agent()
    context = AgentContext(username=user.username, roles=user.roles)
    config = {
        "configurable": {"thread_id": f"eval-{uuid.uuid4()}"},
        "callbacks": [recorder],
    }

    for attempt in range(_MAX_RATE_LIMIT_RETRIES + 1):
        try:
            result = await agent.ainvoke(
                {"messages": [HumanMessage(content=question)]},
                context=context,
                config=config,
            )
            break
        except Exception as exc:
            is_rate_limit = "rate_limit" in str(exc).lower() or "429" in str(exc)
            if not is_rate_limit or attempt == _MAX_RATE_LIMIT_RETRIES:
                raise
            wait_seconds = min(
                _RATE_LIMIT_BACKOFF_SECONDS * (attempt + 1),
                _RATE_LIMIT_MAX_BACKOFF_SECONDS,
            )
            print(
                f"  [rate limited, attempt {attempt + 1}/{_MAX_RATE_LIMIT_RETRIES}, "
                f"retrying in {wait_seconds}s] {question[:60]!r}",
                flush=True,
            )
            recorder.tool_calls.clear()
            await asyncio.sleep(wait_seconds)

    content = result.get("structured_response")
    if content is None:
        # Guardrail short-circuit (PromptInjectionGuardrailMiddleware) — no
        # structured_response is produced; the rejection text is the last
        # message the graph wrote before jumping to "end".
        actual_output = result["messages"][-1].content
    elif type(content) is CompositeContent:
        actual_output = "\n\n".join(_render_content(block) for block in content.blocks)
    else:
        actual_output = _render_content(content)

    return actual_output, recorder.tool_calls


async def build_test_cases(dataset: EvaluationDataset, limit: int | None = None) -> None:
    """Runs goldens in `dataset` through the live agent, in order, inside
    whichever single event loop calls this, and appends the results as
    LLMTestCases back onto the same dataset (dataset.add_test_case).
    `limit`, if given, only runs the first N goldens — useful as a quick
    smoke test before committing to a full, slower/costlier run.

    Must run entirely within one asyncio.run() call: the agent singleton's
    Redis checkpointer and MCP HTTP client bind to whichever loop first
    builds them (see get_agent() in core.py), so calling this once per
    golden from separate asyncio.run() calls would break every case after
    the first.
    """
    goldens = dataset.goldens[:limit] if limit else dataset.goldens
    for i, golden in enumerate(goldens):
        if i > 0:
            # Spread sequential turns out so a modest-tier OpenAI org's TPM
            # budget (each turn is several chained LLM calls) has real room
            # to refill between goldens, on top of run_case's own
            # per-call retry-on-429.
            await asyncio.sleep(15)
        print(f"[{i + 1}/{len(goldens)}] {golden.name}", flush=True)
        username = golden.additional_metadata["username"]
        actual_output, tools_called = await run_case(golden.input, username)
        dataset.add_test_case(
            LLMTestCase(
                name=golden.name,
                input=golden.input,
                actual_output=actual_output,
                expected_output=golden.expected_output,
                tools_called=tools_called,
                expected_tools=golden.expected_tools,
            )
        )
