from fastapi import APIRouter

from db.influx import influx_health
from db.mongo import mongo_health
from db.postgres import postgres_health
from db.redis import redis_health

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    # not sure if we need all 4 checks here but leaving it for now
    services = {
        "postgres": await postgres_health(),
        "mongodb": await mongo_health(),
        "redis": await redis_health(),
        "influxdb": await influx_health(),
    }
    overall = "ok" if all(services.values()) else "degraded"
    return {"status": overall, "services": services}

