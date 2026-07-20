import uuid
from datetime import datetime, timezone

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
    round_tripped = IssueListResponse.model_validate_json(resp.model_dump_json())
    assert round_tripped == resp
    print("PASS: issue_list valid + round-trip")


def test_issue_list_invalid():
    try:
        IssueListResponse(customer_name="Deloitte", issues="not-a-list", **ENVELOPE)
    except ValidationError:
        print("PASS: issue_list invalid payload raises ValidationError")
        return
    raise AssertionError("expected ValidationError for issue_list with issues as a string")


def test_customer_profile_valid():
    resp = CustomerProfileResponse(
        customer_name="Google", fields={"industry": "Tech", "account_tier": "Platinum"}, **ENVELOPE
    )
    assert resp.type == "customer_profile"
    assert CustomerProfileResponse.model_validate_json(resp.model_dump_json()) == resp
    print("PASS: customer_profile valid + round-trip")


def test_customer_profile_invalid():
    try:
        CustomerProfileResponse(customer_name="Google", fields=["not", "a", "dict"], **ENVELOPE)
    except ValidationError:
        print("PASS: customer_profile invalid payload raises ValidationError")
        return
    raise AssertionError("expected ValidationError for customer_profile with fields as a list")


def test_escalation_email_valid():
    resp = EscalationEmailResponse(
        to="recipient@example.com", subject="Urgent: outage", body="Please advise.", **ENVELOPE
    )
    assert resp.type == "escalation_email"
    assert EscalationEmailResponse.model_validate_json(resp.model_dump_json()) == resp
    print("PASS: escalation_email valid + round-trip")


def test_escalation_email_invalid():
    try:
        EscalationEmailResponse(to="recipient@example.com", subject="Urgent", **ENVELOPE)
    except ValidationError:
        print("PASS: escalation_email invalid payload (missing body) raises ValidationError")
        return
    raise AssertionError("expected ValidationError for escalation_email missing body")


def test_bullet_summary_valid():
    resp = BulletSummaryResponse(heading="Issue #3 summary", points=["Opened Monday", "Resolved Tuesday"], **ENVELOPE)
    assert resp.type == "bullet_summary"
    assert BulletSummaryResponse.model_validate_json(resp.model_dump_json()) == resp
    print("PASS: bullet_summary valid + round-trip")


def test_bullet_summary_invalid():
    try:
        BulletSummaryResponse(heading="Issue #3 summary", points="not-a-list", **ENVELOPE)
    except ValidationError:
        print("PASS: bullet_summary invalid payload raises ValidationError")
        return
    raise AssertionError("expected ValidationError for bullet_summary with points as a string")


def test_chat_message_valid():
    resp = ChatMessageResponse(message="I'm doing well, thanks!", **ENVELOPE)
    assert resp.type == "chat_message"
    assert ChatMessageResponse.model_validate_json(resp.model_dump_json()) == resp
    print("PASS: chat_message valid + round-trip")


def test_chat_message_invalid():
    try:
        ChatMessageResponse(**ENVELOPE)  # missing required `message`
    except ValidationError:
        print("PASS: chat_message invalid payload (missing message) raises ValidationError")
        return
    raise AssertionError("expected ValidationError for chat_message missing message")


def test_error_valid():
    resp = ErrorResponse(message="agent failed", code="agent_error", **ENVELOPE)
    assert resp.type == "error"
    assert ErrorResponse.model_validate_json(resp.model_dump_json()) == resp
    print("PASS: error valid + round-trip")


def test_error_invalid():
    try:
        ErrorResponse(message="agent failed", **ENVELOPE)  # missing required `code`
    except ValidationError:
        print("PASS: error invalid payload (missing code) raises ValidationError")
        return
    raise AssertionError("expected ValidationError for error missing code")


def test_discriminated_union_dispatch():
    adapter = TypeAdapter(WsResponse)
    payload = {"type": "chat_message", "message": "hi", **{**ENVELOPE, "timestamp": ENVELOPE["timestamp"].isoformat()}}
    parsed = adapter.validate_python(payload)
    assert isinstance(parsed, ChatMessageResponse)
    print("PASS: discriminated union dispatches known type correctly")

    try:
        adapter.validate_python({**payload, "type": "totally_unknown_type"})
    except ValidationError:
        print("PASS: discriminated union rejects an unknown type value")
        return
    raise AssertionError("expected ValidationError for an unknown discriminator value")


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
    round_tripped = CompositeContent.model_validate_json(composite.model_dump_json())
    assert round_tripped == composite
    print("PASS: composite_content valid + round-trip")


def test_composite_content_invalid():
    try:
        CompositeContent(blocks="not-a-list")
    except ValidationError:
        print("PASS: composite_content invalid payload raises ValidationError")
        return
    raise AssertionError("expected ValidationError for composite_content with blocks as a string")


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
    print("PASS: build_ws_response decomposes composite blocks into distinct WsResponse types")


def test_build_ws_response_escalation_email_placeholder():
    draft = EscalationEmailDraft(subject="Urgent: outage", body="Please advise.")
    response = build_ws_response(draft, ENVELOPE)
    assert isinstance(response, EscalationEmailResponse)
    assert response.to == "recipient@example.com"
    print("PASS: build_ws_response attaches the escalation email placeholder recipient")


def test_resolve_role_context():
    assert resolve_role_context(["admin"]) == "admin"
    assert resolve_role_context(["sales", "admin"]) == "admin"
    assert resolve_role_context(["sales"]) == "sales"
    assert resolve_role_context(["operations"]) == "operations"
    assert resolve_role_context([]) == "support"
    assert resolve_role_context(["some_unknown_role"]) == "some_unknown_role"
    print("PASS: resolve_role_context collapses roles as expected")


if __name__ == "__main__":
    test_issue_list_valid()
    test_issue_list_invalid()
    test_customer_profile_valid()
    test_customer_profile_invalid()
    test_escalation_email_valid()
    test_escalation_email_invalid()
    test_bullet_summary_valid()
    test_bullet_summary_invalid()
    test_chat_message_valid()
    test_chat_message_invalid()
    test_error_valid()
    test_error_invalid()
    test_discriminated_union_dispatch()
    test_composite_content_valid()
    test_composite_content_invalid()
    test_build_ws_response_decomposes_composite_blocks()
    test_build_ws_response_escalation_email_placeholder()
    test_resolve_role_context()
    print("\nAll response_types tests passed.")
