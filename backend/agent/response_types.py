from datetime import datetime
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter


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


class CompositeContent(BaseModel):
    """Use this — and only this — when a single reply genuinely needs more
    than one of the other shapes, because the user asked for more than one
    kind of thing and you called separate tools for each. Example: "Show me
    the company profile for Google and list its issues" requires calling both
    a profile tool and an issues tool, then answering with a CompositeContent
    containing one CustomerProfileContent block AND one IssueListContent
    block — never just the profile block alone, and never two separate
    top-level tool calls instead of this one. Never use this to wrap what is
    really a single-shape answer.
    """

    blocks: list[
        Union[IssueListContent, CustomerProfileContent, EscalationEmailDraft, BulletSummaryContent, ChatMessageContent]
    ] = Field(
        description=(
            "One block per distinct shape actually needed, in the order the user should "
            "see them — every part of a multi-part question must get its own block, none "
            "dropped. Never fabricate a block with no supporting tool result."
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


def _build_ws_response_strict(content: BaseModel, envelope: dict) -> "WsResponse":
    if type(content) is EscalationEmailDraft:
        return EscalationEmailResponse(to=DUMMY_RECIPIENT_EMAIL, **content.model_dump(), **envelope)
    response_cls = CONTENT_TO_RESPONSE.get(type(content))
    if response_cls is None:
        raise ValueError(f"Unrecognized structured_response type: {type(content)!r}")
    return response_cls(**content.model_dump(), **envelope)


# Recovery target for a dict that lost its Pydantic type identity somewhere
# upstream (e.g. a checkpointer round-trip) but still holds valid content —
# deliberately excludes CompositeContent, since a block should never itself
# be a nested composite.
_LEAF_CONTENT_ADAPTER = TypeAdapter(
    Union[IssueListContent, CustomerProfileContent, EscalationEmailDraft, BulletSummaryContent, ChatMessageContent]
)


def _fallback_text(content: Any) -> str:
    message = getattr(content, "message", None)
    if isinstance(message, str) and message:
        return message
    if isinstance(content, dict):
        for key in ("message", "body", "heading"):
            value = content.get(key)
            if isinstance(value, str) and value:
                return value
    return "Sorry, I couldn't format that response properly. Could you rephrase your question?"


def build_ws_response(content: Any, envelope: dict) -> "WsResponse":
    """Maps a single content-only model (one of the 5 shapes above, never
    CompositeContent itself) to its enveloped wire type. Shared by respond()'s
    single-shape path and by each block of a CompositeContent answer, so the
    `to`-placeholder special case and CONTENT_TO_RESPONSE lookup live in one place.

    `content` is expected to already be one of the 5 shapes, but defends
    against it arriving as a plain dict (observed in practice, most likely
    from the Redis/LangGraph checkpointer round-tripping a prior turn's
    structured_response) — first by trying to re-validate it back into the
    correct shape (recovering the real card/table instead of degrading it),
    and only falling back to a plain chat message if that's not possible, so
    a malformed/unrecognized response never surfaces a raw error to the user.
    """
    try:
        return _build_ws_response_strict(content, envelope)
    except Exception:
        pass

    if isinstance(content, dict):
        try:
            recovered = _LEAF_CONTENT_ADAPTER.validate_python(content)
            return _build_ws_response_strict(recovered, envelope)
        except Exception:
            pass

    print(f"[build_ws_response] could not map structured_response to a known shape: {content!r}"[:500])
    return ChatMessageResponse(message=_fallback_text(content), **envelope)


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
