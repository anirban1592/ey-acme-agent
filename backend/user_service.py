import asyncpg
import uuid
from typing import Optional
from models import User

class UserService:
    @staticmethod
    async def validate_user(pool: asyncpg.Pool, keycloak_id: str) -> Optional[User]:
        try:
            user_uuid = uuid.UUID(keycloak_id)
        except ValueError:
            return None

        query = """
            SELECT u.id, u.username, u.email, u.keycloak_id,
                   COALESCE(ARRAY_AGG(r.name) FILTER (WHERE r.name IS NOT NULL), '{}') AS roles
            FROM users u
            LEFT JOIN user_roles ur ON u.id = ur.user_id
            LEFT JOIN roles r ON ur.role_id = r.id
            WHERE u.keycloak_id = $1
            GROUP BY u.id;
        """
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, user_uuid)

        if row:
            data = dict(row)
            if data.get("keycloak_id"):
                data["keycloak_id"] = str(data["keycloak_id"])
            return User(**data)

        return None
