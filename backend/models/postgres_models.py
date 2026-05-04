from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class IncidentStatus(StrEnum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class RootCauseCategory(StrEnum):
    INFRA = "INFRA"
    CODE = "CODE"
    NETWORK = "NETWORK"
    HUMAN_ERROR = "HUMAN_ERROR"
    UNKNOWN = "UNKNOWN"


class Base(DeclarativeBase):
    pass


class WorkItem(Base):
    __tablename__ = "work_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    component_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    component_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    error_code: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=IncidentStatus.OPEN.value, index=True, nullable=False)
    signal_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    mttr_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    rca: Mapped["RCARecord | None"] = relationship(back_populates="work_item", cascade="all, delete-orphan", uselist=False)


class RCARecord(Base):
    __tablename__ = "rca_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    work_item_id: Mapped[int] = mapped_column(ForeignKey("work_items.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    incident_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    incident_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    root_cause_category: Mapped[str] = mapped_column(String(32), nullable=False)
    fix_applied: Mapped[str] = mapped_column(Text, nullable=False)
    prevention_steps: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    work_item: Mapped[WorkItem] = relationship(back_populates="rca")


class SignalIn(BaseModel):
    component_id: str = Field(min_length=1, max_length=128)
    component_type: str = Field(min_length=1, max_length=64)
    error_code: str = Field(min_length=1, max_length=64)
    severity: str = Field(pattern=r"^P[0-2]$")
    message: str = Field(min_length=1, max_length=4096)
    timestamp: datetime

    @field_validator("timestamp")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class StatusTransitionRequest(BaseModel):
    status: IncidentStatus


class RCARequest(BaseModel):
    incident_start: datetime
    incident_end: datetime
    root_cause_category: RootCauseCategory
    fix_applied: str = Field(min_length=20)
    prevention_steps: str = Field(min_length=20)

    @model_validator(mode="after")
    def validate_time_window(self) -> "RCARequest":
        if self.incident_end <= self.incident_start:
            raise ValueError("incident_end must be after incident_start")
        return self


class RCAOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    work_item_id: int
    incident_start: datetime
    incident_end: datetime
    root_cause_category: str
    fix_applied: str
    prevention_steps: str
    created_at: datetime


class WorkItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    component_id: str
    component_type: str
    error_code: str
    severity: str
    message: str
    status: str
    signal_count: int
    start_time: datetime
    end_time: datetime | None
    mttr_minutes: float | None
    created_at: datetime
    updated_at: datetime
    rca: RCAOut | None = None

