import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock

from sqlalchemy import update
from tenacity import RetryError, retry, stop_after_attempt, wait_exponential

from db.influx import write_signal_throughput
from db.mongo import signals_collection
from db.postgres import SessionLocal
from models.mongo_models import RawSignalDocument
from models.postgres_models import IncidentStatus, SignalIn, WorkItem
from services.alerting import strategy_for_component
from services.cache import invalidate_dashboard_cache
from services.metrics import DB_WRITE_FAILURES, INCIDENTS_CREATED, INGEST_QUEUE_DEPTH

logger = logging.getLogger("ims.debounce")

signal_queue: asyncio.Queue[SignalIn] = asyncio.Queue(maxsize=50000)


class SignalCounters:
    def __init__(self) -> None:
        self._lock = Lock()
        self._interval_count = 0
        self._total_count = 0

    def increment(self) -> None:
        with self._lock:
            self._interval_count += 1
            self._total_count += 1

    def snapshot_and_reset(self) -> int:
        with self._lock:
            count = self._interval_count
            self._interval_count = 0
            return count

    def total(self) -> int:
        with self._lock:
            return self._total_count


@dataclass
class DebounceWindow:
    first_seen: datetime
    signals: list[SignalIn] = field(default_factory=list)
    work_item_id: int | None = None


class DebounceEngine:
    def __init__(self, counters: SignalCounters, threshold: int = 100, window_seconds: int = 10) -> None:
        # TODO: maybe make threshold configurable from env later
        self.counters = counters
        self.threshold = threshold
        self.window_seconds = window_seconds
        self.windows: dict[str, DebounceWindow] = {}
        # one lock per component so signals don't race each other
        self.locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._running = True
        self._metrics_task: asyncio.Task | None = None

    async def run(self) -> None:
        self._metrics_task = asyncio.create_task(self._influx_metrics_loop(), name="influx-throughput-loop")
        while self._running:
            try:
                signal = await asyncio.wait_for(signal_queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                await self._expire_windows()
                continue

            self.counters.increment()
            INGEST_QUEUE_DEPTH.set(signal_queue.qsize())
            try:
                try:
                    await self._handle_signal(signal)
                except Exception:
                    logger.exception("Debounce processing failed after retries")
            finally:
                signal_queue.task_done()

    async def stop(self) -> None:
        self._running = False
        if self._metrics_task:
            self._metrics_task.cancel()
        await self._expire_windows(force=True)

    async def _handle_signal(self, signal: SignalIn) -> None:
        lock = self.locks[signal.component_id]
        async with lock:
            now = datetime.now(timezone.utc)
            window = self.windows.get(signal.component_id)
            if window and (now - window.first_seen).total_seconds() > self.window_seconds:
                await self._flush_window(signal.component_id, link_to_work_item=bool(window.work_item_id))
                window = None

            if window is None:
                window = DebounceWindow(first_seen=now)
                self.windows[signal.component_id] = window

            if window.work_item_id:
                await self._persist_raw_signals([signal], window.work_item_id, window.first_seen)
                await self._increment_work_item_signal_count(window.work_item_id, 1)
                await invalidate_dashboard_cache()
                return

            window.signals.append(signal)
            if len(window.signals) >= self.threshold:
                work_item = await self._create_work_item(window.signals)
                window.work_item_id = work_item.id
                await self._persist_raw_signals(window.signals, work_item.id, window.first_seen)
                window.signals.clear()
                strategy_for_component(signal.component_type).alert(signal, work_item.id)
                INCIDENTS_CREATED.labels(severity=signal.severity, component_type=signal.component_type).inc()
                await invalidate_dashboard_cache()

    async def _expire_windows(self, force: bool = False) -> None:
        now = datetime.now(timezone.utc)
        expired = [
            component_id
            for component_id, window in self.windows.items()
            if force or (now - window.first_seen).total_seconds() > self.window_seconds
        ]
        for component_id in expired:
            lock = self.locks[component_id]
            async with lock:
                await self._flush_window(component_id, link_to_work_item=bool(self.windows.get(component_id, None) and self.windows[component_id].work_item_id))

    async def _flush_window(self, component_id: str, link_to_work_item: bool) -> None:
        window = self.windows.pop(component_id, None)
        if not window:
            return
        work_item_id = window.work_item_id if link_to_work_item else None
        if window.signals:
            await self._persist_raw_signals(window.signals, work_item_id, window.first_seen)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.2, min=0.2, max=2))
    async def _create_work_item_retry(self, signals: list[SignalIn]) -> WorkItem:
        first = signals[0]
        async with SessionLocal() as session:
            async with session.begin():
                work_item = WorkItem(
                    component_id=first.component_id,
                    component_type=first.component_type,
                    error_code=first.error_code,
                    severity=first.severity,
                    message=first.message,
                    status=IncidentStatus.OPEN.value,
                    signal_count=len(signals),
                    start_time=min(signal.timestamp for signal in signals),
                )
                session.add(work_item)
                await session.flush()
                await session.refresh(work_item)
                return work_item

    async def _create_work_item(self, signals: list[SignalIn]) -> WorkItem:
        try:
            return await self._create_work_item_retry(signals)
        except RetryError:
            DB_WRITE_FAILURES.labels(db="postgres").inc()
            logger.exception("Failed to create work item after retries")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.2, min=0.2, max=2))
    async def _persist_raw_signals_retry(self, signals: list[SignalIn], work_item_id: int | None, window_start: datetime) -> None:
        docs = [
            RawSignalDocument(
                **signal.model_dump(),
                received_at=datetime.now(timezone.utc),
                work_item_id=work_item_id,
                debounce_window_started_at=window_start,
            ).to_mongo()
            for signal in signals
        ]
        if docs:
            await signals_collection().insert_many(docs, ordered=False)

    async def _persist_raw_signals(self, signals: list[SignalIn], work_item_id: int | None, window_start: datetime) -> None:
        try:
            await self._persist_raw_signals_retry(signals, work_item_id, window_start)
        except RetryError:
            DB_WRITE_FAILURES.labels(db="mongodb").inc()
            logger.exception("Failed to persist raw signals after retries")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.2, min=0.2, max=2))
    async def _increment_work_item_signal_count_retry(self, work_item_id: int, amount: int) -> None:
        async with SessionLocal() as session:
            async with session.begin():
                await session.execute(
                    update(WorkItem)
                    .where(WorkItem.id == work_item_id)
                    .values(signal_count=WorkItem.signal_count + amount)
                )

    async def _increment_work_item_signal_count(self, work_item_id: int, amount: int) -> None:
        try:
            await self._increment_work_item_signal_count_retry(work_item_id, amount)
        except RetryError:
            DB_WRITE_FAILURES.labels(db="postgres").inc()
            logger.exception("Failed to update work item signal count after retries")
            raise

    async def _influx_metrics_loop(self) -> None:
        # write to influx every 5s
        previous_total = 0
        total_seen = 0
        while self._running:
            await asyncio.sleep(5)
            depth = signal_queue.qsize()
            total_seen = self.counters.total()
            rate = (total_seen - previous_total) / 5
            previous_total = total_seen
            try:
                await write_signal_throughput(rate, depth)
            except Exception:
                DB_WRITE_FAILURES.labels(db="influxdb").inc()
                logger.exception("Failed to write InfluxDB throughput metric")
