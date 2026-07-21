import uuid
from datetime import datetime, timezone

import pytest
from pydantic import TypeAdapter, ValidationError

from agent.response_types import (
    BulletSummaryResponse,
    ChatMessageContent,
    ChatMessageResponse,
    CompositeContent,
    CustomerProfileContent,
    CustomerProfileResponse,
    ErrorResponse,
    EscalationEmailDraft,
    EscalationEmailResponse,
    IssueListContent,
    IssueListResponse,
    IssueSummary,
    WsResponse,
    build_ws_response,
    resolve_role_context,
)

ENVELOPE = dict(
    request_id=str(uuid.uuid4()),
    timestamp=datetime.now(timezone.utc),
    role_context="sales",
)


def test_issue_list_valid():
    resp = IssueListResponse(
        customer_name="Deloitte",
        issues=[
            IssueSummary(id=1, title="Login broken", status="open", updated_at=datetime.now(timezone.utc)),
        ],
        **ENVELOPE,
    )
    assert resp.type == "issue_list"
    assert IssueListResponse.model_validate_json(resp.model_dump_json()) == resp


def test_issue_list_invalid():
    with pytest.raises(ValidationError):
        IssueListResponse(customer_name="Deloitte", issues="not-a-list", **ENVELOPE)


def test_customer_profile_valid():
    resp = CustomerProfileResponse(
        customer_name="Google", fields={"industry": "Tech", "account_tier": "Platinum"}, **ENVELOPE
    )
    assert resp.type == "customer_profile"
    assert CustomerProfileResponse.model_validate_json(resp.model_dump_json()) == resp


def test_customer_profile_invalid():
    with pytest.raises(ValidationError):
        CustomerProfileResponse(customer_name="Google", fields=["not", "a", "dict"], **ENVELOPE)


def test_escalation_email_valid():
    resp = EscalationEmailResponse(
        to="recipient@example.com", subject="Urgent: outage", body="Please advise.", **ENVELOPE
    )
    assert resp.type == "escalation_email"
    assert EscalationEmailResponse.model_validate_json(resp.model_dump_json()) == resp


def test_escalation_email_invalid():
    with pytest.raises(ValidationError):
        EscalationEmailResponse(to="recipient@example.com", subject="Urgent", **ENVELOPE)  # missing body


def test_bullet_summary_valid():
    resp = BulletSummaryResponse(heading="Issue #3 summary", points=["Opened Monday", "Resolved Tuesday"], **ENVELOPE)
    assert resp.type == "bullet_summary"
    assert BulletSummaryResponse.model_validate_json(resp.model_dump_json()) == resp


def test_bullet_summary_invalid():
    with pytest.raises(ValidationError):
        BulletSummaryResponse(heading="Issue #3 summary", points="not-a-list", **ENVELOPE)


def test_chat_message_valid():
    resp = ChatMessageResponse(message="I'm doing well, thanks!", **ENVELOPE)
    assert resp.type == "chat_message"
    assert ChatMessageResponse.model_validate_json(resp.model_dump_json()) == resp


def test_chat_message_invalid():
    with pytest.raises(ValidationError):
        ChatMessageResponse(**ENVELOPE)  # missing required `message`


def test_error_valid():
    resp = ErrorResponse(message="agent failed", code="agent_error", **ENVELOPE)
    assert resp.type == "error"
    assert ErrorResponse.model_validate_json(resp.model_dump_json()) == resp


def test_error_invalid():
    with pytest.raises(ValidationError):
        ErrorResponse(message="agent failed", **ENVELOPE)  # missing required `code`


def test_discriminated_union_dispatch():
    adapter = TypeAdapter(WsResponse)
    payload = {"type": "chat_message", "message": "hi", **{**ENVELOPE, "timestamp": ENVELOPE["timestamp"].isoformat()}}
    parsed = adapter.validate_python(payload)
    assert isinstance(parsed, ChatMessageResponse)


def test_discriminated_union_rejects_unknown_type():
    adapter = TypeAdapter(WsResponse)
    payload = {"type": "chat_message", "message": "hi", **{**ENVELOPE, "timestamp": ENVELOPE["timestamp"].isoformat()}}
    with pytest.raises(ValidationError):
        adapter.validate_python({**payload, "type": "totally_unknown_type"})


def test_composite_content_valid():
    composite = CompositeContent(
        blocks=[
            IssueListContent(
                customer_name="Deloitte",
                issues=[IssueSummary(id=1, title="Login broken", status="open", updated_at=datetime.now(timezone.utc))],
            ),
            CustomerProfileContent(customer_name="Deloitte", fields={"industry": "Consulting"}),
        ]
    )
    assert len(composite.blocks) == 2
    assert CompositeContent.model_validate_json(composite.model_dump_json()) == composite


def test_composite_content_invalid():
    with pytest.raises(ValidationError):
        CompositeContent(blocks="not-a-list")


def test_build_ws_response_decomposes_composite_blocks():
    composite = CompositeContent(
        blocks=[
            IssueListContent(
                customer_name="Deloitte",
                issues=[IssueSummary(id=1, title="Login broken", status="open", updated_at=datetime.now(timezone.utc))],
            ),
            ChatMessageContent(message="Anything else I can help with?"),
        ]
    )
    responses = [build_ws_response(block, {**ENVELOPE, "request_id": str(uuid.uuid4())}) for block in composite.blocks]
    assert len(responses) == 2
    assert isinstance(responses[0], IssueListResponse)
    assert isinstance(responses[1], ChatMessageResponse)
    assert responses[0].request_id != responses[1].request_id


def test_build_ws_response_escalation_email_placeholder():
    draft = EscalationEmailDraft(subject="Urgent: outage", body="Please advise.")
    response = build_ws_response(draft, ENVELOPE)
    assert isinstance(response, EscalationEmailResponse)
    assert response.to == "recipient@example.com"


def test_build_ws_response_recovers_dict_with_recognizable_shape():
    response = build_ws_response({"message": "hi there"}, ENVELOPE)
    assert isinstance(response, ChatMessageResponse)
    assert response.message == "hi there"


def test_build_ws_response_falls_back_on_unrecognized_dict():
    response = build_ws_response({"foo": "bar"}, ENVELOPE)
    assert isinstance(response, ChatMessageResponse)
    assert response.message


@pytest.mark.parametrize(
    "roles,expected",
    [
        (["admin"], "admin"),
        (["sales", "admin"], "admin"),
        (["sales"], "sales"),
        (["operations"], "operations"),
        ([], "support"),
        (["some_unknown_role"], "some_unknown_role"),
    ],
)
def test_resolve_role_context(roles, expected):
    assert resolve_role_context(roles) == expected
