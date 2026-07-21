from datetime import date

import pytest
from pydantic import ValidationError

from models.models import CustomerProfile, User


def test_user_valid():
    user = User(id=1, username="alice", email="alice@example.com", keycloak_id="abc-123", roles=["admin"])
    assert user.roles == ["admin"]


def test_user_allows_null_email_and_keycloak_id():
    user = User(id=2, username="bob", email=None, keycloak_id=None, roles=["sales"])
    assert user.email is None
    assert user.keycloak_id is None


def test_user_invalid_missing_required_field():
    with pytest.raises(ValidationError):
        User(id=1, username="alice", email=None, keycloak_id=None)  # missing `roles`


def test_user_invalid_wrong_type_for_roles():
    with pytest.raises(ValidationError):
        User(id=1, username="alice", email=None, keycloak_id=None, roles="admin")


def test_customer_profile_valid_with_all_fields_optional():
    profile = CustomerProfile(
        customer_name="Deloitte",
        industry=None,
        account_tier=None,
        headquarters=None,
        employee_count=None,
        relationship_since=None,
        account_manager=None,
        support_lead=None,
        operations_lead=None,
        executive_sponsor=None,
        primary_contact_name=None,
        primary_contact_title=None,
        primary_contact_email=None,
        contract_value_arr=None,
        renewal_date=None,
        products_services=None,
        payment_terms=None,
        sentiment=None,
        risk_level=None,
        notes=None,
    )
    assert profile.customer_name == "Deloitte"


def test_customer_profile_invalid_wrong_type_for_date_field():
    with pytest.raises(ValidationError):
        CustomerProfile(
            customer_name="Deloitte",
            industry=None,
            account_tier=None,
            headquarters=None,
            employee_count=None,
            relationship_since="not-a-date",
            account_manager=None,
            support_lead=None,
            operations_lead=None,
            executive_sponsor=None,
            primary_contact_name=None,
            primary_contact_title=None,
            primary_contact_email=None,
            contract_value_arr=None,
            renewal_date=date(2026, 1, 1),
            products_services=None,
            payment_terms=None,
            sentiment=None,
            risk_level=None,
            notes=None,
        )
