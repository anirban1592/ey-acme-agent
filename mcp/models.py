from datetime import datetime

from pydantic import BaseModel


class Issue(BaseModel):
    id: int
    customer_name: str
    title: str
    description: str | None
    status: str
    domain: str | None
    persona: str | None
    reporter: str | None
    last_updated_by: str | None
    created_at: datetime
    updated_at: datetime
