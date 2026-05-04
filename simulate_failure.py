import asyncio
import os
from datetime import datetime, timezone

import httpx
from jose import jwt

API_BASE_URL = os.getenv("IMS_API_BASE_URL", "http://localhost:8000")
JWT_SECRET = os.getenv("IMS_JWT_SECRET", "change-me-super-secret")
JWT_ALGORITHM = os.getenv("IMS_JWT_ALGORITHM", "HS256")
JWT_TOKEN = os.getenv("IMS_JWT_TOKEN")


def token() -> str:
    if JWT_TOKEN:
        return JWT_TOKEN
    now = int(datetime.now(timezone.utc).timestamp())
    return jwt.encode({"sub": "simulator", "iat": now, "exp": now + 3600}, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def send_signals(client: httpx.AsyncClient, component_id: str, component_type: str, count: int, error_code: str, severity: str) -> None:
    # hardcoded for now, will clean up later
    for index in range(1, count + 1):
        payload = {
            "component_id": component_id,
            "component_type": component_type,
            "error_code": error_code,
            "severity": severity,
            "message": f"Simulated {component_type} failure signal {index}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        resp = await client.post("/api/ingest", json=payload)
        resp.raise_for_status()
        if index % 10 == 0:
            print(f"Sent {index}/{count} signals for {component_id}")
        await asyncio.sleep(0.025)


async def main() -> None:
    headers = {"Authorization": f"Bearer {token()}", "X-Request-ID": "simulate-failure"}
    async with httpx.AsyncClient(base_url=API_BASE_URL, headers=headers, timeout=10) as client:
        print("Sending 150 signals for RDBMS_PRIMARY_01")
        await send_signals(client, "RDBMS_PRIMARY_01", "RDBMS", 150, "DB_CONN_TIMEOUT", "P0")
        # Sending 120 signals to cross the 100-signal debounce threshold
        print("Sending 120 signals for MCP_HOST_02")
        await send_signals(client, "MCP_HOST_02", "MCP_HOST", 120, "MCP_HEARTBEAT_LOST", "P0")
    print("Simulation complete")


if __name__ == "__main__":
    asyncio.run(main())

