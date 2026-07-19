import os

from langchain.agents import create_agent
from langchain.tools import tool, ToolRuntime
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from .context import AgentContext

from services import CustomerService

# Owns its own ChatOpenAI instance rather than importing core.py's `model` —
# avoids a core.py <-> customer_profile.py circular import (core.py imports
# consult_customer_profile_agent below), and mirrors this codebase's existing
# convention of modules owning their own config independently (mcp/db.py
# duplicates backend/db.py's DSN/pool logic rather than sharing it).
api_key = os.getenv("OPENAI_API_KEY") or "mock-key"
_model = ChatOpenAI(
    model=os.getenv("OPENAI_MODEL_NAME", "gpt-5.1"),
    temperature=0.0,
    openai_api_key=api_key,
)


@tool
async def get_customer_profile(customer_name: str) -> str:
    """Look up a customer's CRM/account profile by name — industry, account
    tier, account manager, contract value, risk level, sentiment, notes, etc.
    This is account/relationship data, NOT issue-tracking data."""
    profile = await CustomerService.get_customer_profile(customer_name)
    return profile.model_dump_json() if profile else f"No profile found for '{customer_name}'."


customer_profile_agent = create_agent(
    model=_model,
    tools=[get_customer_profile],
    system_prompt=(
        "You answer questions about a customer's CRM/account profile using "
        "the get_customer_profile tool, then summarize the relevant fields "
        "concisely for the caller."
    ),
    name="customer_profile_agent",
)


@tool
async def consult_customer_profile_agent(runtime: ToolRuntime[AgentContext], query: str) -> str:
    """Delegate a customer CRM/account-profile question (industry, account
    tier, account manager, contract value, risk level, sentiment, notes) to
    the specialist customer-profile sub-agent. Do not use this for
    issue-tracking questions — use retrieve_customer_profile for those."""
    if "admin" not in runtime.context.roles:
        raise PermissionError(
            "consult_customer_profile_agent is restricted to users with the 'admin' role."
        )
    result = await customer_profile_agent.ainvoke({"messages": [HumanMessage(content=query)]})
    return result["messages"][-1].content
