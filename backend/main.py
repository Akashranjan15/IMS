import asyncio
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.responses import PlainTextResponse

from db.influx import close_influx, init_influx
from db.mongo import close_mongo, ensure_mongo_indexes, init_mongo
from db.postgres import close_postgres, init_postgres
from db.redis import close_redis, init_redis
from routers import health, incidents, ingest
from services.debounce import DebounceEngine, SignalCounters, signal_queue
from services.metrics import INGEST_QUEUE_DEPTH
from services.rate_limit import limiter

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(request_id)s] %(name)s - %(message)s",
)
# TODO: move this to a config file

old_record_factory = logging.getLogRecordFactory()


def record_factory(*args, **kwargs):
    record = old_record_factory(*args, **kwargs)
    if not hasattr(record, "request_id"):
        record.request_id = "-"
    return record


logging.setLogRecordFactory(record_factory)
logger = logging.getLogger("ims.main")


async def throughput_loop(counters: SignalCounters) -> None:
    while True:
        await asyncio.sleep(5)
        current = counters.snapshot_and_reset()
        signals_per_sec = current / 5
        INGEST_QUEUE_DEPTH.set(signal_queue.qsize())
        print(f"Throughput: {signals_per_sec:.2f} signals/sec", flush=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_postgres()
    await init_mongo()
    await ensure_mongo_indexes()
    await init_redis()
    await init_influx()

    counters = SignalCounters()
    engine = DebounceEngine(counters=counters)
    app.state.signal_queue = signal_queue
    app.state.counters = counters
    app.state.debounce_engine = engine
    app.state.debounce_task = asyncio.create_task(engine.run(), name="debounce-engine")
    app.state.throughput_task = asyncio.create_task(throughput_loop(counters), name="throughput-loop")

    logger.info("IMS backend started")
    try:
        yield
    finally:
        for task_name in ("debounce_task", "throughput_task"):
            task = getattr(app.state, task_name, None)
            if task:
                task.cancel()
        await engine.stop()
        await close_influx()
        await close_redis()
        await close_mongo()
        await close_postgres()
        logger.info("IMS backend stopped")


app = FastAPI(title="Incident Management System", version="1.0.0", lifespan=lifespan)
app.state.limiter = limiter
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return PlainTextResponse("rate limit exceeded", status_code=429)


app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
app.add_middleware(SlowAPIMiddleware)

allowed_origins = [origin.strip() for origin in os.getenv("IMS_ALLOWED_ORIGINS", "http://localhost:3000").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()
    response: Response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-Ms"] = f"{(time.perf_counter() - started) * 1000:.2f}"
    return response


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


app.include_router(ingest.router)
app.include_router(incidents.router)
app.include_router(health.router)
