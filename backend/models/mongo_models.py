from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RawSignalDocument(BaseModel):
    component_id: str
    component_type: str
    error_code: str
    severity: str
    message: str
    timestamp: datetime
    received_at: datetime
    work_item_id: int | None = None
    debounce_window_started_at: datetime | None = None

    def to_mongo(self) -> dict[str, Any]:
        return self.model_dump()

