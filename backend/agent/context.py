from dataclasses import dataclass


@dataclass
class AgentContext:
    """Per-invocation, non-LLM-controlled data derived from the authenticated user.

    Passed via create_agent's context_schema/agent.ainvoke's context= — never
    part of the LLM's message history or tool-call arguments, so it cannot be
    influenced by prompt injection.
    """

    username: str
    roles: list[str]
