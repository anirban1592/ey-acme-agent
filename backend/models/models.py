from datetime import date
from decimal import Decimal

from pydantic import BaseModel

class User(BaseModel):
    id: int
    username: str
    email: str | None
    keycloak_id: str | None
    roles: list[str]

class CustomerProfile(BaseModel):
    customer_name: str
    industry: str | None
    account_tier: str | None
    headquarters: str | None
    employee_count: int | None
    relationship_since: date | None
    account_manager: str | None
    support_lead: str | None
    operations_lead: str | None
    executive_sponsor: str | None
    primary_contact_name: str | None
    primary_contact_title: str | None
    primary_contact_email: str | None
    contract_value_arr: Decimal | None
    renewal_date: date | None
    products_services: str | None
    payment_terms: str | None
    sentiment: str | None
    risk_level: str | None
    notes: str | None
