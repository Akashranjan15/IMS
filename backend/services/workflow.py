import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.postgres_models import IncidentStatus, RCARecord, WorkItem
from services.metrics import STATE_TRANSITIONS

logger = logging.getLogger("ims.workflow")


class IncidentState(ABC):
    status: IncidentStatus
    allowed: set[IncidentStatus]

    @abstractmethod
    async def before_transition(self, work_item: WorkItem, target: IncidentStatus, session: AsyncSession) -> None:
        raise NotImplementedError

    async def transition(self, work_item: WorkItem, target: IncidentStatus, session: AsyncSession) -> WorkItem:
        # check allowed transitions first
        if target not in self.allowed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot transition from {work_item.status} to {target.value}",
            )
        await self.before_transition(work_item, target, session)
        old = work_item.status
        work_item.status = target.value
        if target == IncidentStatus.RESOLVED:
            work_item.end_time = datetime.now(timezone.utc)
            work_item.mttr_minutes = max((work_item.end_time - work_item.start_time).total_seconds() / 60, 0)
        logger.info("Incident %s transitioned %s -> %s", work_item.id, old, target.value)
        STATE_TRANSITIONS.labels(from_status=old, to_status=target.value).inc()
        return work_item


class OpenState(IncidentState):
    status = IncidentStatus.OPEN
    allowed = {IncidentStatus.INVESTIGATING}

    async def before_transition(self, work_item: WorkItem, target: IncidentStatus, session: AsyncSession) -> None:
        return None


class InvestigatingState(IncidentState):
    status = IncidentStatus.INVESTIGATING
    allowed = {IncidentStatus.RESOLVED}

    async def before_transition(self, work_item: WorkItem, target: IncidentStatus, session: AsyncSession) -> None:
        return None


class ResolvedState(IncidentState):
    status = IncidentStatus.RESOLVED
    allowed = {IncidentStatus.CLOSED}

    async def before_transition(self, work_item: WorkItem, target: IncidentStatus, session: AsyncSession) -> None:
        result = await session.execute(select(RCARecord).where(RCARecord.work_item_id == work_item.id))
        rca = result.scalar_one_or_none()
        if not rca:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="RCA is required before closing an incident")
        if len(rca.fix_applied.strip()) < 20 or len(rca.prevention_steps.strip()) < 20:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="RCA is incomplete")


class ClosedState(IncidentState):
    status = IncidentStatus.CLOSED
    allowed = set()

    async def before_transition(self, work_item: WorkItem, target: IncidentStatus, session: AsyncSession) -> None:
        # FIXME: double check this edge case when work_item is already closed
        return None


STATE_MAP: dict[str, IncidentState] = {
    IncidentStatus.OPEN.value: OpenState(),
    IncidentStatus.INVESTIGATING.value: InvestigatingState(),
    IncidentStatus.RESOLVED.value: ResolvedState(),
    IncidentStatus.CLOSED.value: ClosedState(),
}


async def transition_work_item(session: AsyncSession, incident_id: int, target: IncidentStatus) -> WorkItem:
    async with session.begin():
        result = await session.execute(
            select(WorkItem)
            .options(selectinload(WorkItem.rca))
            .where(WorkItem.id == incident_id)
            .with_for_update()
        )
        work_item = result.scalar_one_or_none()
        if not work_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
        state = STATE_MAP[work_item.status]
        await state.transition(work_item, target, session)
        session.add(work_item)
    await session.refresh(work_item, ["rca"])
    return work_item

