from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(UTC)


class HealthState(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class IncidentStatus(StrEnum):
    QUEUED = "queued"
    INVESTIGATING = "investigating"
    REMEDIATING = "remediating"
    VERIFYING = "verifying"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    FAILED = "failed"


class Service(BaseModel):
    id: str
    name: str
    health: HealthState = HealthState.HEALTHY
    cpu_percent: float = 20
    memory_percent: float = 35
    error_rate: float = 0.1
    latency_ms: int = 45
    uptime_seconds: int = 86400
    dependencies: list[str] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)
    fault: str | None = None
    restart_count: int = 0


class AgentEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    incident_id: str
    timestamp: datetime = Field(default_factory=utcnow)
    event_type: str
    summary: str
    status: str = "success"
    tool: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class Incident(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    service_id: str
    scenario: str
    trigger: str
    status: IncidentStatus = IncidentStatus.QUEUED
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    probable_cause: str | None = None
    evidence: list[str] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    verification: str | None = None
    escalation: dict[str, Any] | None = None
    report: dict[str, Any] | None = None


class TriggerRequest(BaseModel):
    scenario: str = Field(pattern="^(recoverable|unsafe)$")

