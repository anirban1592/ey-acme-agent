import asyncio
import os

from redis.asyncio import Redis as AsyncRedis
from langgraph.checkpoint.redis import AsyncRedisSaver


def _redis_url() -> str:
    host = os.getenv("REDIS_HOST", "redis")
    port = os.getenv("REDIS_PORT", "6379")
    return f"redis://{host}:{port}"


_checkpointer = None
_checkpointer_lock = asyncio.Lock()
_redis_client = None


async def get_checkpointer():
    """
    Builds the AsyncRedisSaver (and its underlying Redis client) on first
    use and caches it, guarded by a lock so concurrent callers can't race
    and build it more than once — mirrors core.py's get_agent(). asetup()
    creates the RediSearch indices the checkpointer needs; it only ever
    runs once here, inside the lock, before the singleton is published.
    """
    global _checkpointer, _redis_client
    if _checkpointer is None:
        async with _checkpointer_lock:
            if _checkpointer is None:
                _redis_client = AsyncRedis.from_url(_redis_url())
                saver = AsyncRedisSaver(redis_client=_redis_client)
                await saver.asetup()
                _checkpointer = saver
    return _checkpointer


async def close_checkpointer():
    """Closes the underlying Redis connection on app shutdown."""
    global _checkpointer, _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
    _checkpointer = None
