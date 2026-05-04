import os

import redis.asyncio as redis

REDIS_DSN = os.getenv("REDIS_DSN", "redis://localhost:6379/0")

client: redis.Redis | None = None


async def init_redis() -> None:
    global client
    client = redis.from_url(REDIS_DSN, encoding="utf-8", decode_responses=True)
    await client.ping()


def redis_client() -> redis.Redis:
    if client is None:
        raise RuntimeError("Redis is not initialized")
    return client


async def redis_health() -> bool:
    try:
        return bool(client and await client.ping())
    except Exception:
        return False


async def close_redis() -> None:
    if client:
        await client.aclose()

