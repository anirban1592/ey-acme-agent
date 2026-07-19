from pydantic import BaseModel

class User(BaseModel):
    id: int
    username: str
    email: str | None
    keycloak_id: str | None
    roles: list[str]
