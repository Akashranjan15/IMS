import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, status

from models.postgres_models import SignalIn
from services.auth import require_jwt
from services.debounce import signal_queue
from services.metrics import SIGNALS_ACCEPTED, SIGNALS_REJECTED
from services.rate_limit import limiter

router = APIRouter(prefix="/api", tags=["ingest"], dependencies=[Depends(require_jwt)])


@router.post("/ingest", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("1000/minute")
async def ingest_signal(request: Request, signal: SignalIn):
    try:
        signal_queue.put_nowait(signal)
    except asyncio.QueueFull as exc:  # type: ignore[name-defined]
        SIGNALS_REJECTED.labels(reason="queue_full").inc()
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Ingest queue is full") from exc
    SIGNALS_ACCEPTED.labels(severity=signal.severity, component_type=signal.component_type).inc()
    return {"accepted": True, "queue_depth": signal_queue.qsize()}
