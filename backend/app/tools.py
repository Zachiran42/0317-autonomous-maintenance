from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.models import AgentEvent, HealthState
from app.observability import log_event
from app.policy import ActionPolicy
from app.repository import Repository
from app.simulator import Simulator


class IncidentTools:
    def __init__(self, simulator: Simulator, repository: Repository, policy: ActionPolicy) -> None:
        self.simulator = simulator
        self.repository = repository
        self.policy = policy
        self.incident_id: str | None = None

    def bind(self, incident_id: str) -> IncidentTools:
        self.incident_id = incident_id
        return self

    def _call(self, name: str, fn: Callable[[], Any]) -> Any:
        if not self.incident_id:
            raise RuntimeError("Tools must be bound to an incident")
        log_event("tool_call", incident_id=self.incident_id, tool=name, status="started")
        try:
            result = fn()
            self.repository.append_event(
                AgentEvent(
                    incident_id=self.incident_id,
                    event_type="tool_call",
                    tool=name,
                    summary=f"{name} completed",
                    data={"result": result},
                )
            )
            log_event("tool_call", incident_id=self.incident_id, tool=name, status="success")
            return result
        except Exception as exc:
            self.repository.append_event(
                AgentEvent(
                    incident_id=self.incident_id,
                    event_type="tool_call",
                    tool=name,
                    summary=f"{name} failed: {exc}",
                    status="error",
                )
            )
            log_event("tool_call", incident_id=self.incident_id, tool=name, status="error")
            raise

    def get_service_health(self, service_id: str) -> dict[str, Any]:
        """Return current health, latency, and error rate for a simulated service."""
        return self._call("get_service_health", lambda: {
            "service_id": service_id,
            "health": self.simulator.get(service_id).health,
            "latency_ms": self.simulator.get(service_id).latency_ms,
            "error_rate": self.simulator.get(service_id).error_rate,
        })

    def get_recent_logs(self, service_id: str) -> dict[str, Any]:
        """Return the most recent structured log messages for a service."""
        return self._call("get_recent_logs", lambda: {
            "service_id": service_id, "logs": self.simulator.get(service_id).logs[-20:]
        })

    def get_metrics(self, service_id: str) -> dict[str, Any]:
        """Return CPU, memory, errors, and latency metrics for a service."""
        return self._call("get_metrics", lambda: {
            "service_id": service_id,
            "cpu_percent": self.simulator.get(service_id).cpu_percent,
            "memory_percent": self.simulator.get(service_id).memory_percent,
            "error_rate": self.simulator.get(service_id).error_rate,
            "latency_ms": self.simulator.get(service_id).latency_ms,
        })

    def get_dependency_health(self, service_id: str) -> dict[str, Any]:
        """Return health for every declared dependency of a service."""
        def inspect() -> dict[str, Any]:
            service = self.simulator.get(service_id)
            return {dependency: self.simulator.get(dependency).health for dependency in service.dependencies}
        return self._call("get_dependency_health", inspect)

    def search_runbooks(self, query: str) -> dict[str, Any]:
        """Search curated runbooks for safe remediation guidance."""
        def search() -> dict[str, Any]:
            text = query.lower()
            if "deadlock" in text or "worker" in text:
                return {"matches": [{"id": "RB-017", "action": "restart stateless web-api"}]}
            if "corrupt" in text or "checksum" in text:
                return {"matches": [{"id": "RB-042", "action": "preserve evidence and escalate"}]}
            return {"matches": []}
        return self._call("search_runbooks", search)

    def search_previous_incidents(self, query: str) -> dict[str, Any]:
        """Search previous incidents by probable cause and return concise matches."""
        return self._call("search_previous_incidents", lambda: {
            "matches": [
                {"id": item.id, "cause": item.probable_cause, "status": item.status}
                for item in self.repository.list_incidents()
                if query.lower() in (item.probable_cause or "").lower()
            ][:5]
        })

    def restart_service(self, service_id: str) -> dict[str, Any]:
        """Restart a stateless service only when the code-enforced policy allows it."""
        def restart() -> dict[str, Any]:
            self.policy.enforce("restart_stateless_service", service_id=service_id)
            service = self.simulator.restart(service_id)
            return {"service_id": service_id, "restart_count": service.restart_count}
        return self._call("restart_service", restart)

    def verify_service_health(self, service_id: str) -> dict[str, Any]:
        """Verify that a service is healthy after a remediation action."""
        def verify() -> dict[str, Any]:
            self.policy.enforce("verify_health", service_id=service_id)
            service = self.simulator.get(service_id)
            return {"service_id": service_id, "healthy": service.health == HealthState.HEALTHY,
                    "health": service.health, "latency_ms": service.latency_ms}
        return self._call("verify_service_health", verify)

    def create_incident_report(self, data: dict[str, Any]) -> dict[str, Any]:
        """Persist the final auditable incident report."""
        def create() -> dict[str, Any]:
            self.policy.enforce("create_report")
            incident = self.repository.get_incident(self.incident_id or "")
            if not incident:
                raise KeyError("Incident not found")
            incident.report = data
            self.repository.save_incident(incident)
            return {"incident_id": incident.id, "stored": True}
        return self._call("create_incident_report", create)

    def escalate_incident(self, data: dict[str, Any]) -> dict[str, Any]:
        """Persist an escalation and recommended next steps without destructive action."""
        def escalate() -> dict[str, Any]:
            self.policy.enforce("escalate")
            incident = self.repository.get_incident(self.incident_id or "")
            if not incident:
                raise KeyError("Incident not found")
            incident.escalation = data
            self.repository.save_incident(incident)
            return {"incident_id": incident.id, "escalated": True}
        return self._call("escalate_incident", escalate)
