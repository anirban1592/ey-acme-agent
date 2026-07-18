import logging
import os
import asyncpg

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
