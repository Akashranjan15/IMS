import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from tenacity import RetryError, retry, retry_if_not_exception_type, stop_after_attempt, wait_exponential

from db.mongo import signals_collection
from db.postgres import get_session
from models.postgres_models import RCAOut, RCARecord, RCARequest, StatusTransitionRequest, WorkItem, WorkItemOut
from services.auth import require_jwt
from services.cache import get_dashboard_cache, invalidate_dashboard_cache, set_dashboard_cache
from services.metrics import DB_WRITE_FAILURES
from services.workflow import transition_work_item

logger = logging.getLogger("ims.incidents")
router = APIRouter(prefix="/api/incidents", tags=["incidents"], dependencies=[Depends(require_jwt)])


def serialize_work_item(work_item: WorkItem) -> dict[str, Any]:
    return WorkItemOut.model_validate(work_item).model_dump(mode="json")


@router.get("", response_model=list[WorkItemOut])
async def list_incidents(session: AsyncSession = Depends(get_session)):
    # TODO: add pagination later, this will be slow with lots of incidents
    cached = await get_dashboard_cache()
    if cached is not None:
        return cached

    result = await session.execute(select(WorkItem).options(selectinload(WorkItem.rca)).order_by(desc(WorkItem.created_at)))
    work_items = result.scalars().all()
    severity_rank = {"P0": 0, "P1": 1, "P2": 2}
    payload = sorted((serialize_work_item(item) for item in work_items), key=lambda item: (severity_rank.get(item["severity"], 99), item["created_at"]), reverse=False)
    await set_dashboard_cache(payload)
    return payload


@router.get("/{incident_id}")
async def get_incident(incident_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(WorkItem).options(selectinload(WorkItem.rca)).where(WorkItem.id == incident_id))
    work_item = result.scalar_one_or_none()
    if not work_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    cursor = signals_collection().find({"work_item_id": incident_id}).sort("timestamp", 1)
    raw_signals = []
    async for document in cursor:
        document["_id"] = str(document["_id"])
        raw_signals.append(document)

    return {"incident": serialize_work_item(work_item), "signals": raw_signals}


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.2, min=0.2, max=2),
    retry=retry_if_not_exception_type(HTTPException),
)
async def transition_with_retry(session: AsyncSession, incident_id: int, payload: StatusTransitionRequest) -> WorkItem:
    return await transition_work_item(session, incident_id, payload.status)


@router.patch("/{incident_id}/status", response_model=WorkItemOut)
async def update_status(incident_id: int, payload: StatusTransitionRequest, session: AsyncSession = Depends(get_session)):
    try:
        incident = await transition_with_retry(session, incident_id, payload)
    except RetryError as exc:
        DB_WRITE_FAILURES.labels(db="postgres").inc()
        logger.exception("Status transition failed after retries")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="PostgreSQL write failed after retries") from exc
    await invalidate_dashboard_cache()
    return incident


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.2, min=0.2, max=2),
    retry=retry_if_not_exception_type(HTTPException),
)
async def upsert_rca_with_retry(session: AsyncSession, incident_id: int, payload: RCARequest) -> RCARecord:
    async with session.begin():
        result = await session.execute(select(WorkItem).where(WorkItem.id == incident_id).with_for_update())
        work_item = result.scalar_one_or_none()
        if not work_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

        existing = await session.execute(select(RCARecord).where(RCARecord.work_item_id == incident_id))
        rca = existing.scalar_one_or_none()
        if rca is None:
            rca = RCARecord(work_item_id=incident_id, **payload.model_dump())
        else:
            for field, value in payload.model_dump().items():
                setattr(rca, field, value)
        session.add(rca)
        await session.flush()
        await session.refresh(rca)
        return rca


@router.post("/{incident_id}/rca", response_model=RCAOut, status_code=status.HTTP_201_CREATED)
async def submit_rca(incident_id: int, payload: RCARequest, session: AsyncSession = Depends(get_session)):
    try:
        rca = await upsert_rca_with_retry(session, incident_id, payload)
    except RetryError as exc:
        DB_WRITE_FAILURES.labels(db="postgres").inc()
        logger.exception("RCA write failed after retries")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="PostgreSQL write failed after retries") from exc
    await invalidate_dashboard_cache()
    return rca
