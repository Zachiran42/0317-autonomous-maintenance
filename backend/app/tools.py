from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

from app.models import ActionExecution, GateDecision, MaintenanceEvent, StepStatus
from app.observability import log_event
from app.policy import EvidenceGate
from app.repository import Repository
from app.simulator import Simulator


def structured(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


class MaintenanceTools:
    def __init__(self, simulator: Simulator, repository: Repository, gate: EvidenceGate) -> None:
        self.simulator = simulator
        self.repository = repository
        self.gate = gate
        self.maintenance_id: str | None = None

    def bind(self, maintenance_id: str) -> MaintenanceTools:
        self.maintenance_id = maintenance_id
        return self

    def _read_node(self, target: str, reader: Callable[[Any], dict[str, Any]]) -> dict[str, Any]:
        """Return a recoverable observation when a planner names a non-node target."""
        try:
            return reader(self.simulator.get(target))
        except KeyError as exc:
            return {
                "target": target,
                "available": False,
                "error": str(exc),
                "allowed_targets": [node["id"] for node in self.simulator.topology()["nodes"]],
            }

    def _call(
        self,
        name: str,
        target: str,
        fn: Callable[[], Any],
        *,
        idempotent: bool = False,
    ) -> Any:
        if not self.maintenance_id:
            raise RuntimeError("Tools must be bound to a maintenance run")
        self.gate.enforce_action(name)
        key = f"{self.maintenance_id}:{name}:{target}"
        if idempotent:
            previous = self.repository.get_action_by_key(key)
            if previous and previous.status == "success":
                self.repository.append_event(
                    MaintenanceEvent(
                        maintenance_id=self.maintenance_id,
                        action_id=previous.action_id,
                        event_type="idempotent_replay",
                        target=target,
                        tool=name,
                        summary=f"{name} already completed; duplicate execution skipped",
                        evidence={"idempotency_key": key},
                    )
                )
                return previous.result
        action_id = f"act-{uuid4().hex[:10]}"
        log_event(
            "tool_call",
            maintenance_id=self.maintenance_id,
            action_id=action_id,
            tool=name,
            target=target,
            status="started",
        )
        try:
            result = structured(fn())
            if idempotent:
                self.repository.save_action(
                    ActionExecution(
                        action_id=action_id,
                        maintenance_id=self.maintenance_id,
                        idempotency_key=key,
                        action=name,
                        target=target,
                        status="success",
                        result=result,
                    )
                )
            self.repository.append_event(
                MaintenanceEvent(
                    maintenance_id=self.maintenance_id,
                    action_id=action_id,
                    event_type="tool_call",
                    target=target,
                    tool=name,
                    summary=f"{name} completed",
                    evidence={"result": result},
                )
            )
            log_event(
                "tool_call",
                maintenance_id=self.maintenance_id,
                action_id=action_id,
                tool=name,
                target=target,
                status="success",
            )
            return result
        except Exception as exc:
            if idempotent:
                self.repository.save_action(
                    ActionExecution(
                        action_id=action_id,
                        maintenance_id=self.maintenance_id,
                        idempotency_key=key,
                        action=name,
                        target=target,
                        status="error",
                        result={"error": str(exc)},
                    )
                )
            self.repository.append_event(
                MaintenanceEvent(
                    maintenance_id=self.maintenance_id,
                    action_id=action_id,
                    event_type="tool_call",
                    target=target,
                    tool=name,
                    summary=f"{name} failed: {exc}",
                    status="error",
                )
            )
            log_event(
                "tool_call",
                maintenance_id=self.maintenance_id,
                action_id=action_id,
                tool=name,
                target=target,
                status="error",
            )
            raise

    def get_change_request(self) -> dict[str, Any]:
        """Return the approved maintenance request and current structured plan."""

        def get() -> dict[str, Any]:
            run = self.repository.get_run(self.maintenance_id or "")
            if not run:
                raise KeyError("Maintenance run not found")
            return {
                "maintenance_id": run.id,
                "request": run.request,
                "approved": run.approved,
                "status": run.status,
                "plan": [step.model_dump(mode="json") for step in run.plan],
            }

        return self._call("get_change_request", "maintenance", get)

    def get_topology(self) -> dict[str, Any]:
        """Discover the current infrastructure topology and dependencies."""
        return self._call("get_topology", "infrastructure", self.simulator.topology)

    def get_service_health(self, target: str) -> dict[str, Any]:
        """Read current health and lifecycle state for one infrastructure node."""
        return self._call(
            "get_service_health",
            target,
            lambda: self._read_node(
                target,
                lambda node: {
                    "target": target,
                    "available": True,
                    "health": node.health,
                    "state": node.state,
                    "version": node.version,
                    "desired_version": node.desired_version,
                    "in_load_balancer": node.in_load_balancer,
                },
            ),
        )

    def get_metrics(self, target: str) -> dict[str, Any]:
        """Read CPU, memory, latency, and error-rate evidence for a node."""
        return self._call(
            "get_metrics",
            target,
            lambda: self._read_node(
                target,
                lambda node: {
                    "target": target,
                    "available": True,
                    "cpu_percent": node.cpu_percent,
                    "memory_percent": node.memory_percent,
                    "latency_ms": node.latency_ms,
                    "error_rate": node.error_rate,
                },
            ),
        )

    def get_recent_logs(self, target: str) -> dict[str, Any]:
        """Read recent generated logs for a node."""
        return self._call(
            "get_recent_logs",
            target,
            lambda: self._read_node(
                target,
                lambda node: {"target": target, "available": True, "logs": node.logs[-20:]},
            ),
        )

    def search_runbooks(self, query: str) -> dict[str, Any]:
        """Search generated maintenance runbooks for relevant procedures."""

        def search() -> dict[str, Any]:
            text = query.lower()
            matches: list[dict[str, Any]] = []
            if "web" in text or "rolling" in text:
                matches.append(
                    {
                        "id": "RB-ROLLING-12",
                        "title": "Zero-downtime web rolling update",
                        "requires": ["capacity", "drain", "rollback point", "synthetic test"],
                    }
                )
            if "database" in text:
                matches.append(
                    {
                        "id": "RB-DB-08",
                        "title": "Evidence-gated database maintenance",
                        "requires": ["verified backup", "full target-version redundancy"],
                    }
                )
            return {"matches": matches}

        return self._call("search_runbooks", "runbooks", search)

    def search_maintenance_history(self, query: str) -> dict[str, Any]:
        """Search previous maintenance reports for concise relevant outcomes."""
        return self._call(
            "search_maintenance_history",
            "history",
            lambda: {
                "matches": [
                    {
                        "maintenance_id": run.id,
                        "status": run.status,
                        "summary": (run.report or {}).get("outcome"),
                    }
                    for run in self.repository.list_runs()
                    if run.id != self.maintenance_id and query.lower() in run.request.lower()
                ][:5]
            },
        )

    def check_capacity(self, excluding: str | None = None) -> dict[str, Any]:
        """Verify remaining web capacity, optionally while one node is drained."""
        return self._call(
            "check_capacity",
            excluding or "web-tier",
            lambda: self.simulator.check_capacity(excluding),
        )

    def check_application_availability(self) -> dict[str, Any]:
        """Measure whether the application still has healthy serving web capacity."""
        return self._call(
            "check_application_availability",
            "web-tier",
            self.simulator.check_application_availability,
        )

    def evaluate_evidence(self, gate_name: str, target: str) -> dict[str, Any]:
        """Evaluate a deterministic Evidence Gate and persist every observed requirement."""

        def evaluate() -> GateDecision:
            run = self.repository.get_run(self.maintenance_id or "")
            if not run:
                raise KeyError("Maintenance run not found")
            decision = self.gate.evaluate(gate_name, target, run.id, run.approved)
            run.gate_decisions.append(decision)
            self.repository.save_run(run)
            return decision

        return self._call("evaluate_evidence", target, evaluate)

    def create_snapshot(self, target: str = "database") -> dict[str, Any]:
        """Create and verify a simulated database snapshot before changes."""
        return self._call(
            "create_snapshot",
            target,
            lambda: self.simulator.create_snapshot(self.maintenance_id or ""),
            idempotent=True,
        )

    def drain_node(self, target: str) -> dict[str, Any]:
        """Drain a web node only after the remaining-capacity gate passes."""

        def drain() -> Any:
            decision = self.gate.evaluate("drain_node", target, self.maintenance_id or "")
            self.gate.enforce_gate(decision)
            return self.simulator.drain_node(target)

        return self._call("drain_node", target, drain, idempotent=True)

    def create_rollback_point(self, target: str) -> dict[str, Any]:
        """Capture verified pre-change state used only by this maintenance run."""
        return self._call(
            "create_rollback_point",
            target,
            lambda: self.simulator.create_rollback_point(self.maintenance_id or "", target),
            idempotent=True,
        )

    def apply_maintenance(self, target: str) -> dict[str, Any]:
        """Apply an approved simulated update after drain and rollback evidence pass."""

        def apply() -> Any:
            decision = self.gate.evaluate("apply_web_change", target, self.maintenance_id or "")
            self.gate.enforce_gate(decision)
            return self.simulator.apply_maintenance(self.maintenance_id or "", target)

        return self._call("apply_maintenance", target, apply, idempotent=True)

    def restart_service(self, target: str) -> dict[str, Any]:
        """Restart the changed simulated service."""
        return self._call(
            "restart_service",
            target,
            lambda: self.simulator.restart_service(target),
            idempotent=True,
        )

    def run_health_check(self, target: str) -> dict[str, Any]:
        """Run a readiness/health verification against a target."""
        return self._call(
            "run_health_check", target, lambda: self.simulator.run_health_check(target)
        )

    def run_synthetic_test(self, target: str) -> dict[str, Any]:
        """Run a functional synthetic transaction and enforce its error threshold."""
        return self._call(
            "run_synthetic_test", target, lambda: self.simulator.run_synthetic_test(target)
        )

    def restore_node_to_pool(self, target: str) -> dict[str, Any]:
        """Restore a verified healthy node to the simulated load balancer."""
        return self._call(
            "restore_node_to_pool",
            target,
            lambda: self.simulator.restore_node_to_pool(target),
            idempotent=True,
        )

    def rollback_change(self, target: str) -> dict[str, Any]:
        """Rollback only the state created by this run using its verified rollback point."""

        def rollback() -> Any:
            decision = self.gate.evaluate("rollback", target, self.maintenance_id or "")
            self.gate.enforce_gate(decision)
            return self.simulator.rollback_change(self.maintenance_id or "", target)

        return self._call("rollback_change", target, rollback, idempotent=True)

    def verify_rollback(self, target: str) -> dict[str, Any]:
        """Verify version, health, and load-balancer membership after rollback."""
        return self._call(
            "verify_rollback",
            target,
            lambda: self.simulator.verify_rollback(self.maintenance_id or "", target),
        )

    def apply_database_maintenance(self, target: str = "database") -> dict[str, Any]:
        """Apply approved database maintenance after its deterministic gate passes."""

        def apply() -> Any:
            decision = self.gate.evaluate("database_change", target, self.maintenance_id or "")
            self.gate.enforce_gate(decision)
            return self.simulator.apply_database_maintenance(self.maintenance_id or "")

        return self._call("apply_database_maintenance", target, apply, idempotent=True)

    def defer_change(self, target: str, reason: str) -> dict[str, Any]:
        """Persist a safely deferred plan step and its blocking evidence."""

        def defer() -> dict[str, Any]:
            run = self.repository.get_run(self.maintenance_id or "")
            if not run:
                raise KeyError("Maintenance run not found")
            for step in run.plan:
                if step.target == target and step.status == StepStatus.PENDING:
                    step.status = StepStatus.DEFERRED
                    step.decision_summary = reason
            blocked = {"target": target, "reason": reason}
            run.blocked_operations.append(blocked)
            run.decision_summaries.append(reason)
            self.repository.save_run(run)
            return blocked

        return self._call("defer_change", target, defer, idempotent=True)

    def create_maintenance_report(self, report: dict[str, Any]) -> dict[str, Any]:
        """Persist a professional final maintenance report and audit outcome."""

        def create() -> dict[str, Any]:
            run = self.repository.get_run(self.maintenance_id or "")
            if not run:
                raise KeyError("Maintenance run not found")
            run.report = report
            self.repository.save_run(run)
            return {"maintenance_id": run.id, "stored": True}

        return self._call("create_maintenance_report", "report", create, idempotent=True)

    def attempt_restricted_action(self, action: str) -> None:
        """Test-only boundary proving restricted/unknown actions fail closed."""
        self.gate.enforce_action(action)
