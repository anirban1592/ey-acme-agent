import logging
import os

import asyncpg

from models import Issue, IssueUpdate, IssueWithUpdates

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
       s.name AS status, i.persona,
       ru.username AS reporter, uu.username AS last_updated_by,
       i.created_at, i.updated_at
FROM issues i
JOIN customers c ON i.customer_id = c.id
JOIN statuses s ON i.status_id = s.id
LEFT JOIN users ru ON i.reporter_id = ru.id
LEFT JOIN users uu ON i.last_updated_by_id = uu.id
WHERE c.name ILIKE $1
{persona_filter}
ORDER BY i.created_at DESC;
"""


async def fetch_customer_issues(
    pool: asyncpg.Pool, customer_name: str, roles: list[str]
) -> list[Issue]:
    normalized_roles = [r.strip() for r in roles if r and r.strip()]
    is_admin = any(r.lower() == "admin" for r in normalized_roles)
    query = _ISSUES_QUERY.format(
        persona_filter="" if is_admin else "  AND i.persona ILIKE ANY($2::text[])"
    )
    args = [customer_name] if is_admin else [customer_name, normalized_roles]
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *args)
    return [Issue.model_validate(dict(row)) for row in rows]


_ISSUE_WITH_UPDATES_QUERY = """
SELECT i.id AS issue_id, c.name AS customer_name, i.title AS issue_title,
       i.description AS issue_description, s.name AS status, i.persona,
       ru.username AS reporter, uu.username AS last_updated_by,
       i.created_at AS issue_created_at, i.updated_at AS issue_updated_at,
       iu.id AS update_id, iu.comment AS update_comment,
       iu.created_at AS update_created_at
FROM issues i
JOIN customers c ON i.customer_id = c.id
JOIN statuses s ON i.status_id = s.id
LEFT JOIN users ru ON i.reporter_id = ru.id
LEFT JOIN users uu ON i.last_updated_by_id = uu.id
LEFT JOIN issue_updates iu ON iu.issue_id = i.id
WHERE i.id = $1
{persona_filter}
ORDER BY iu.created_at DESC NULLS LAST;
"""


async def fetch_issue_updates(
    pool: asyncpg.Pool, issue_id: int, roles: list[str]
) -> IssueWithUpdates | None:
    normalized_roles = [r.strip() for r in roles if r and r.strip()]
    is_admin = any(r.lower() == "admin" for r in normalized_roles)
    query = _ISSUE_WITH_UPDATES_QUERY.format(
        persona_filter="" if is_admin else "  AND i.persona ILIKE ANY($2::text[])"
    )
    args = [issue_id] if is_admin else [issue_id, normalized_roles]
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *args)
    if not rows:
        return None

    first = rows[0]
    issue = Issue.model_validate(
        {
            "id": first["issue_id"],
            "customer_name": first["customer_name"],
            "title": first["issue_title"],
            "description": first["issue_description"],
            "status": first["status"],
            "persona": first["persona"],
            "reporter": first["reporter"],
            "last_updated_by": first["last_updated_by"],
            "created_at": first["issue_created_at"],
            "updated_at": first["issue_updated_at"],
        }
    )
    updates = [
        IssueUpdate.model_validate(
            {
                "id": row["update_id"],
                "issue_id": first["issue_id"],
                "comment": row["update_comment"],
                "created_at": row["update_created_at"],
            }
        )
        for row in rows
        if row["update_id"] is not None
    ]
    return IssueWithUpdates(issue=issue, updates=updates)
