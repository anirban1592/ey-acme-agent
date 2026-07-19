import asyncio
import os
from pathlib import Path

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain.tools import tool
from langchain_core.messages import HumanMessage

from ..response_types import DUMMY_RECIPIENT_EMAIL, EscalationEmailContent, EscalationEmailDraft

_SKILLS_DIR = Path(__file__).parent / "skills"
_SKILL_FILES = {
    "internal_email": _SKILLS_DIR / "internal_email" / "SKILL.md",
    "customer_email": _SKILLS_DIR / "customer_email" / "SKILL.md",
}

ESCALATION_SYSTEM_PROMPT = (
    "You are an escalation email-drafting agent. Given a request to draft an "
    "escalation or notification email, first decide who the recipient is:\n"
    "- Internal team/colleague (IT support, sales, marketing, engineering, "
    "operations) → use the 'internal_email' skill.\n"
    "- External customer/account (e.g. Deloitte, Google) → use the "
    "'customer_email' skill.\n\n"
    "Call load_skill with the chosen skill name to retrieve its tone "
    "options and structure guidance, pick the single best-fitting tone for "
    "the situation, then produce a subject line and a body following that "
    "tone's guidance. Do not claim the email has been sent, since a human "
    "still needs to review and send it — the recipient address is filled "
    "in separately, not by you."
)


@tool
def load_skill(skill_name: str) -> str:
    """Load a specialized email-writing skill's guidance (tone options and
    structure) by name.

    Available skills:
    - internal_email: escalation/status emails to internal teams (IT
      support, sales, marketing, engineering, operations).
    - customer_email: escalation/notification emails to an external
      customer/account (e.g. Deloitte, Google).
    """
    path = _SKILL_FILES.get(skill_name)
    if path is None:
        return f"Unknown skill '{skill_name}'. Available skills: {', '.join(_SKILL_FILES)}."
    return path.read_text()


_escalation_agent = None
_escalation_agent_lock = asyncio.Lock()


async def get_escalation_agent():
    """
    Builds the escalation email-drafting sub-agent on first use and caches
    it, guarded by a lock so concurrent callers can't race and build it more
    than once (mirrors core.py's get_agent()).
    """
    global _escalation_agent
    if _escalation_agent is None:
        async with _escalation_agent_lock:
            if _escalation_agent is None:
                _escalation_agent = create_agent(
                    model=os.getenv("ESCALATION_AGENT_MODEL", "openai:gpt-5-mini"),
                    tools=[load_skill],
                    system_prompt=ESCALATION_SYSTEM_PROMPT,
                    response_format=ToolStrategy(EscalationEmailDraft),
                    name="escalation_agent",
                )
    return _escalation_agent


@tool
async def consult_escalation_agent(query: str) -> str:
    """Delegate an escalation-email drafting request to the specialist
    escalation agent, which picks the right skill (internal team vs.
    external customer) and tone, then drafts a complete email (subject +
    body) for a human to review and send. Use this whenever the user asks
    to escalate, notify, or draft an email about an issue or account."""
    agent = await get_escalation_agent()
    result = await agent.ainvoke({"messages": [HumanMessage(content=query)]})
    draft: EscalationEmailDraft = result["structured_response"]
    content = EscalationEmailContent(to=DUMMY_RECIPIENT_EMAIL, **draft.model_dump())
    return content.model_dump_json()
