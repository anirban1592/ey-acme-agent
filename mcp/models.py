from datetime import datetime

from pydantic import BaseModel


class Issue(BaseModel):
    id: int
    customer_name: str
    title: str
    description: str | None
    status: str
    persona: str | None
    reporter: str | None
    last_updated_by: str | None
    created_at: datetime
    updated_at: datetime


class IssueUpdate(BaseModel):
    id: int
    issue_id: int
    comment: str
    created_at: datetime


class IssueWithUpdates(BaseModel):
    issue: Issue
    updates: list[IssueUpdate]
