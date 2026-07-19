from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class BaseResponse(BaseModel):
    """Envelope fields shared by every typed WebSocket reply. Always
    supplied/overwritten server-side in respond() — never LLM-controlled,
    mirroring the RBAC convention of never trusting the model for
    security/consistency-critical fields (see inject_role_interceptor).
    """

    request_id: str
    timestamp: datetime
    role_context: Literal["sales", "admin", "support", "operations"]


# Fixed placeholder recipient for every escalation email — no real recipient
# lookup exists in this codebase today, and neither sub-agent nor main agent
# LLM is ever allowed to invent a plausible-looking address in its place.
DUMMY_RECIPIENT_EMAIL = "recipient@example.com"


class IssueSummary(BaseModel):
    id: int
    title: str
    status: str
    updated_at: datetime


class IssueListContent(BaseModel):
    customer_name: str
    issues: list[IssueSummary] = Field(
        description="The issues to show, copied verbatim (id/title/status/updated_at) from the tool result."
    )


class CustomerProfileContent(BaseModel):
    customer_name: str
    fields: dict[str, str | None] = Field(
        description="Every other profile field the tool returned, stringified, copied verbatim — do not alter values."
    )


class EscalationEmailDraft(BaseModel):
    """response_format for both the escalation sub-agent AND the main
    agent — deliberately has no `to` field in either case. The recipient is
    never something an LLM should be inventing; respond() always attaches
    the shared DUMMY_RECIPIENT_EMAIL placeholder itself, in Python, after
    the fact."""

    subject: str
    body: str


class EscalationEmailContent(EscalationEmailDraft):
    to: str


class BulletSummaryContent(BaseModel):
    heading: str
    points: list[str] = Field(
        description="Synthesized bullet points copied verbatim from the tool result — do not alter facts/values."
    )


class ChatMessageContent(BaseModel):
    message: str = Field(
        description=(
            "The exact reply text to show the user directly, written as if you were "
            "speaking to them — natural, direct conversational text. This is NOT a "
            "description of your plan, reasoning, or intent; it is the actual message."
        )
    )


class IssueListResponse(BaseResponse, IssueListContent):
    type: Literal["issue_list"] = "issue_list"


class CustomerProfileResponse(BaseResponse, CustomerProfileContent):
    type: Literal["customer_profile"] = "customer_profile"


class EscalationEmailResponse(BaseResponse, EscalationEmailContent):
    type: Literal["escalation_email"] = "escalation_email"


class BulletSummaryResponse(BaseResponse, BulletSummaryContent):
    type: Literal["bullet_summary"] = "bullet_summary"


class ChatMessageResponse(BaseResponse, ChatMessageContent):
    type: Literal["chat_message"] = "chat_message"


class ErrorResponse(BaseResponse):
    type: Literal["error"] = "error"
    message: str
    code: str


WsResponse = Annotated[
    Union[
        IssueListResponse,
        CustomerProfileResponse,
        EscalationEmailResponse,
        BulletSummaryResponse,
        ChatMessageResponse,
        ErrorResponse,
    ],
    Field(discriminator="type"),
]

# Maps the content-only model returned as `structured_response` by the main
# agent to the enveloped wire type it should be wrapped into.
# EscalationEmailDraft is deliberately absent here — respond() special-cases
# it, since building an EscalationEmailResponse also requires attaching
# DUMMY_RECIPIENT_EMAIL, not just copying fields through.
CONTENT_TO_RESPONSE: dict[type[BaseModel], type[BaseResponse]] = {
    IssueListContent: IssueListResponse,
    CustomerProfileContent: CustomerProfileResponse,
    BulletSummaryContent: BulletSummaryResponse,
    ChatMessageContent: ChatMessageResponse,
}


def resolve_role_context(roles: list[str]) -> str:
    """Collapses a user's possibly-multiple roles into the single
    role_context value the frontend gates rendering on. Admin bypasses
    (mirrors the existing RBAC admin-bypass-if-anywhere-in-roles convention);
    otherwise the first recognized role wins; otherwise falls back to
    whatever role string is present, or "support" if roles is empty.
    """
    if "admin" in roles:
        return "admin"
    for role in roles:
        if role in ("sales", "support", "operations"):
            return role
    return roles[0] if roles else "support"
