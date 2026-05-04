import logging
from abc import ABC, abstractmethod

from models.postgres_models import SignalIn

logger = logging.getLogger("ims.alerting")


class AlertStrategy(ABC):
    @abstractmethod
    def alert(self, signal: SignalIn, work_item_id: int) -> None:
        raise NotImplementedError


class CriticalAlertStrategy(AlertStrategy):
    def alert(self, signal: SignalIn, work_item_id: int) -> None:
        logger.critical("P0 incident %s for %s: %s", work_item_id, signal.component_id, signal.message)
        print(f"CRITICAL ALERT: incident={work_item_id} component={signal.component_id} type={signal.component_type}", flush=True)


class ErrorAlertStrategy(AlertStrategy):
    def alert(self, signal: SignalIn, work_item_id: int) -> None:
        logger.error("P1 incident %s for %s: %s", work_item_id, signal.component_id, signal.message)


class WarningAlertStrategy(AlertStrategy):
    def alert(self, signal: SignalIn, work_item_id: int) -> None:
        logger.warning("P2 incident %s for %s: %s", work_item_id, signal.component_id, signal.message)


def strategy_for_component(component_type: str) -> AlertStrategy:
    normalized = component_type.upper()
    if normalized in {"RDBMS", "MCP_HOST"}:
        return CriticalAlertStrategy()
    if normalized in {"ASYNC_QUEUE", "API"}:
        return ErrorAlertStrategy()
    if normalized in {"CACHE", "NOSQL"}:
        return WarningAlertStrategy()
    return WarningAlertStrategy()

