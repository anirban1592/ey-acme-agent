import os

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain.tools import tool, ToolRuntime
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from .context import AgentContext
from .response_types import CustomerProfileContent

from services import CustomerService




@tool
async def get_customer_profile(runtime: ToolRuntime[AgentContext], customer_name: str) -> str:
    """Look up a customer's CRM/account profile by name — industry, account
    tier, account manager, contract value, risk level, sentiment, notes, etc.
    This is account/relationship data, NOT issue-tracking data."""
    if "admin" not in runtime.context.roles:
        raise PermissionError(
            "consult_customer_profile_agent is restricted to users with the 'admin' role."
        )
    profile = await CustomerService.get_customer_profile(customer_name)
    return profile.model_dump_json() if profile else f"No profile found for '{customer_name}'."


customer_profile_agent = create_agent(
    model=os.getenv("CUSTOMER_PROFILE_AGENT_MODEL", "openai:gpt-5-mini"),
    tools=[get_customer_profile],
    system_prompt=(
        "You answer questions about a customer's CRM/account profile using "
        "the get_customer_profile tool. Report the customer_name and a "
        "fields dict containing every other field the tool returned, with "
        "every value converted to a string (or left null if the tool's "
        "value was null). If the tool reports no profile was found, still "
        "report the customer_name you looked up, and use an empty fields "
        "dict."
    ),
    response_format=ToolStrategy(CustomerProfileContent),
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
    content: CustomerProfileContent = result["structured_response"]
    return content.model_dump_json()
