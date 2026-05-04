import os
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase

MONGO_DSN = os.getenv("MONGO_DSN", "mongodb://ims:ims_password@localhost:27017/?authSource=admin")
MONGO_DB = os.getenv("MONGO_DB", "ims")

client: AsyncIOMotorClient | None = None
database: AsyncIOMotorDatabase | None = None


async def init_mongo() -> None:
    global client, database
    client = AsyncIOMotorClient(MONGO_DSN, uuidRepresentation="standard")
    database = client[MONGO_DB]
    await client.admin.command("ping")


def signals_collection() -> AsyncIOMotorCollection:
    if database is None:
        raise RuntimeError("MongoDB is not initialized")
    return database["signals"]


async def ensure_mongo_indexes() -> None:
    collection = signals_collection()
    await collection.create_index("component_id")
    await collection.create_index("work_item_id")
    await collection.create_index("received_at")


async def mongo_health() -> bool:
    try:
        if client is None:
            return False
        result: dict[str, Any] = await client.admin.command("ping")
        return result.get("ok") == 1
    except Exception:
        return False


async def close_mongo() -> None:
    if client:
        client.close()

