import os
from datetime import datetime, timezone

from influxdb_client import Point
from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync

INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "ims-influx-token")
INFLUX_ORG = os.getenv("INFLUX_ORG", "ims-org")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "ims-metrics")

client: InfluxDBClientAsync | None = None


async def init_influx() -> None:
    global client
    client = InfluxDBClientAsync(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    await client.ping()


async def write_signal_throughput(signals_per_second: float, queue_depth: int) -> None:
    if client is None:
        raise RuntimeError("InfluxDB is not initialized")
    point = (
        Point("signal_throughput")
        .tag("service", "ims-backend")
        .field("signals_per_second", float(signals_per_second))
        .field("queue_depth", int(queue_depth))
        .time(datetime.now(timezone.utc))
    )
    write_api = client.write_api()
    await write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)


async def influx_health() -> bool:
    try:
        return bool(client and await client.ping())
    except Exception:
        return False


async def close_influx() -> None:
    if client:
        await client.close()

