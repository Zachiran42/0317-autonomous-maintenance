from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(UTC)


class TransitionError(ValueError):
    pass


class HealthState(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class NodeState(StrEnum):
    HEALTHY = "healthy"
    DRAINING = "draining"
    MAINTENANCE = "maintenance"
    STARTING = "starting"
    VERIFYING = "verifying"
    ROLLED_BACK = "rolled_back"
    DEFERRED = "deferred"


class MaintenanceStatus(StrEnum):
    RECEIVED = "received"
    PLANNING = "planning"
    PREFLIGHT = "preflight"
    READY = "ready"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    ROLLING_BACK = "rolling_back"
    REPLANNING = "replanning"
    DEFERRED = "deferred"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"
    ESCALATED = "escalated"


ALLOWED_TRANSITIONS: dict[MaintenanceStatus, set[MaintenanceStatus]] = {
    MaintenanceStatus.RECEIVED: {MaintenanceStatus.PLANNING, MaintenanceStatus.FAILED},
    MaintenanceStatus.PLANNING: {MaintenanceStatus.PREFLIGHT, MaintenanceStatus.FAILED},
    MaintenanceStatus.PREFLIGHT: {
        MaintenanceStatus.READY,
        MaintenanceStatus.DEFERRED,
        MaintenanceStatus.FAILED,
    },
    MaintenanceStatus.READY: {MaintenanceStatus.EXECUTING, MaintenanceStatus.FAILED},
    MaintenanceStatus.EXECUTING: {
        MaintenanceStatus.VERIFYING,
        MaintenanceStatus.ROLLING_BACK,
        MaintenanceStatus.REPLANNING,
        MaintenanceStatus.COMPLETED,
        MaintenanceStatus.COMPLETED_WITH_WARNINGS,
        MaintenanceStatus.FAILED,
    },
    MaintenanceStatus.VERIFYING: {
        MaintenanceStatus.EXECUTING,
        MaintenanceStatus.ROLLING_BACK,
        MaintenanceStatus.FAILED,
    },
    MaintenanceStatus.ROLLING_BACK: {
        MaintenanceStatus.REPLANNING,
        MaintenanceStatus.FAILED,
        MaintenanceStatus.ESCALATED,
    },
    MaintenanceStatus.REPLANNING: {
        MaintenanceStatus.EXECUTING,
        MaintenanceStatus.DEFERRED,
        MaintenanceStatus.COMPLETED_WITH_WARNINGS,
        MaintenanceStatus.FAILED,
    },
    MaintenanceStatus.DEFERRED: {MaintenanceStatus.COMPLETED_WITH_WARNINGS},
    MaintenanceStatus.COMPLETED: set(),
    MaintenanceStatus.COMPLETED_WITH_WARNINGS: set(),
    MaintenanceStatus.FAILED: set(),
    MaintenanceStatus.ESCALATED: set(),
}


class StepStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    DEFERRED = "deferred"
    BLOCKED = "blocked"


class GateOutcome(StrEnum):
    PASS = "pass"
    FAIL = "fail"


class InfrastructureNode(BaseModel):
    id: str
    name: str
    kind: str
    health: HealthState = HealthState.HEALTHY
    state: NodeState = NodeState.HEALTHY
    version: str = "1.0.0"
    desired_version: str = "1.1.0"
    in_load_balancer: bool = True
    cpu_percent: float = 20
    memory_percent: float = 35
    error_rate: float = 0.1
    latency_ms: int = 45
    capacity_units: int = 50
    dependencies: list[str] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)
    active_change_id: str | None = None
    injected_fault: str | None = None


class EvidenceItem(BaseModel):
    key: str
    label: str
    passed: bool
    observed: Any
    required: Any


class GateDecision(BaseModel):
    gate: str
    target: str
    outcome: GateOutcome
    summary: str
    evidence: list[EvidenceItem]
    evaluated_at: datetime = Field(default_factory=utcnow)


class PlanStep(BaseModel):
    id: str = Field(default_factory=lambda: f"step-{uuid4().hex[:8]}")
    order: int
    target: str
    action: str
    objective: str
    status: StepStatus = StepStatus.PENDING
    depends_on: list[str] = Field(default_factory=list)
    decision_summary: str | None = None


class MaintenanceEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    maintenance_id: str
    action_id: str | None = None
    timestamp: datetime = Field(default_factory=utcnow)
    event_type: str
    target: str | None = None
    summary: str
    status: str = "success"
    tool: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class ActionExecution(BaseModel):
    action_id: str
    maintenance_id: str
    idempotency_key: str
    action: str
    target: str
    status: str
    result: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)


class MaintenanceRun(BaseModel):
    id: str = Field(default_factory=lambda: f"mw-{uuid4().hex[:12]}")
    request: str
    approved: bool = True
    window_start: datetime = Field(default_factory=utcnow)
    window_end: datetime | None = None
    status: MaintenanceStatus = MaintenanceStatus.RECEIVED
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    plan: list[PlanStep] = Field(default_factory=list)
    dependency_graph: dict[str, list[str]] = Field(default_factory=dict)
    initial_evidence: list[EvidenceItem] = Field(default_factory=list)
    gate_decisions: list[GateDecision] = Field(default_factory=list)
    actions_executed: list[str] = Field(default_factory=list)
    rollback_information: list[dict[str, Any]] = Field(default_factory=list)
    blocked_operations: list[dict[str, Any]] = Field(default_factory=list)
    decision_summaries: list[str] = Field(default_factory=list)
    processed_event_ids: list[str] = Field(default_factory=list)
    human_interventions: int = 0
    availability_preserved: bool = True
    report: dict[str, Any] | None = None

    def transition(self, next_status: MaintenanceStatus) -> None:
        if next_status not in ALLOWED_TRANSITIONS[self.status]:
            raise TransitionError(f"Invalid transition: {self.status} -> {next_status}")
        self.status = next_status
        self.updated_at = utcnow()
        if next_status == MaintenanceStatus.EXECUTING and self.started_at is None:
            self.started_at = utcnow()
        if next_status in {
            MaintenanceStatus.COMPLETED,
            MaintenanceStatus.COMPLETED_WITH_WARNINGS,
            MaintenanceStatus.FAILED,
            MaintenanceStatus.ESCALATED,
        }:
            self.completed_at = utcnow()


class CreateMaintenanceRequest(BaseModel):
    request: str = Field(
        default=(
            "Update the web tier and perform the approved database maintenance during tonight's "
            "maintenance window. Preserve service availability where possible. Validate every "
            "target before continuing and rollback failed changes."
        ),
        min_length=20,
        max_length=4000,
    )
    approved: bool = True
    event_id: str | None = None

