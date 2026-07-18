import logging
import os

import asyncpg

from models import Issue

logger = logging.getLogger(__name__)


def _dsn() -> str:
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    host = os.getenv("POSTGRES_HOST", "postgres")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "issuesdb")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


async def create_pool() -> asyncpg.Pool:
    pool = await asyncpg.create_pool(
        dsn=_dsn(),
        min_size=int(os.getenv("DB_POOL_MIN_SIZE", "1")),
        max_size=int(os.getenv("DB_POOL_MAX_SIZE", "5")),
    )
    logger.info("Database connection pool created")
    return pool


_ISSUES_QUERY = """
SELECT i.id, c.name AS customer_name, i.title, i.description,
       s.name AS status, i.domain, i.persona,
       ru.username AS reporter, uu.username AS last_updated_by,
       i.created_at, i.updated_at
FROM issues i
JOIN customers c ON i.customer_id = c.id
JOIN statuses s ON i.status_id = s.id
LEFT JOIN users ru ON i.reporter_id = ru.id
LEFT JOIN users uu ON i.last_updated_by_id = uu.id
WHERE c.name ILIKE $1
{domain_filter}
ORDER BY i.created_at DESC;
"""


async def fetch_customer_issues(
    pool: asyncpg.Pool, customer_name: str, role: str
) -> list[Issue]:
    is_admin = role.strip().lower() == "admin"
    query = _ISSUES_QUERY.format(
        domain_filter="" if is_admin else "  AND i.domain ILIKE $2"
    )
    args = [customer_name] if is_admin else [customer_name, role]
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *args)
    return [Issue.model_validate(dict(row)) for row in rows]
