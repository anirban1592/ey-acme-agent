import asyncio
import logging
import os

import asyncpg

from models import CustomerProfile

logger = logging.getLogger(__name__)


def _dsn() -> str:
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    host = os.getenv("POSTGRES_HOST", "postgres")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "issuesdb")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


_pool: asyncpg.Pool | None = None
_pool_lock = asyncio.Lock()


async def _get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        async with _pool_lock:
            if _pool is None:
                _pool = await asyncpg.create_pool(
                    dsn=_dsn(),
                    min_size=int(os.getenv("DB_POOL_MIN_SIZE", "1")),
                    max_size=int(os.getenv("DB_POOL_MAX_SIZE", "5")),
                )
                logger.info("CustomerService: database connection pool created")
    return _pool


_PROFILE_QUERY = """
    SELECT c.name AS customer_name,
           cd.industry, cd.account_tier, cd.headquarters, cd.employee_count,
           cd.relationship_since, cd.account_manager, cd.support_lead,
           cd.operations_lead, cd.executive_sponsor, cd.primary_contact_name,
           cd.primary_contact_title, cd.primary_contact_email,
           cd.contract_value_arr, cd.renewal_date, cd.products_services,
           cd.payment_terms, cd.sentiment, cd.risk_level, cd.notes
    FROM customers c
    JOIN customer_details cd ON cd.customer_id = c.id
    WHERE c.name ILIKE $1;
"""


class CustomerService:
    @staticmethod
    async def get_customer_profile(customer_name: str) -> CustomerProfile | None:
        pool = await _get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(_PROFILE_QUERY, customer_name)
        if row:
            return CustomerProfile.model_validate(dict(row))
        return None
