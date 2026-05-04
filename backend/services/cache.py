import json
from typing import Any

from db.redis import redis_client

DASHBOARD_CACHE_KEY = "ims:dashboard:incidents"
DASHBOARD_CACHE_TTL_SECONDS = 30


async def get_dashboard_cache() -> list[dict[str, Any]] | None:
    value = await redis_client().get(DASHBOARD_CACHE_KEY)
    if not value:
        return None
    return json.loads(value)


async def set_dashboard_cache(payload: list[dict[str, Any]]) -> None:
    await redis_client().set(DASHBOARD_CACHE_KEY, json.dumps(payload, default=str), ex=DASHBOARD_CACHE_TTL_SECONDS)


async def invalidate_dashboard_cache() -> None:
    await redis_client().delete(DASHBOARD_CACHE_KEY)

