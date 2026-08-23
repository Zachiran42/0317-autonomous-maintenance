from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar


class PolicyDecision(StrEnum):
    ALLOW = "allow"
    ESCALATE = "escalate"


@dataclass(frozen=True)
class PolicyResult:
    decision: PolicyDecision
    reason: str


class ActionPolicy:
    allowed: ClassVar[set[str]] = {
        "inspect_health",
        "inspect_logs",
        "inspect_metrics",
        "inspect_dependencies",
        "search_runbooks",
        "search_incidents",
        "restart_stateless_service",
        "verify_health",
        "create_report",
        "escalate",
    }
    forbidden: ClassVar[set[str]] = {
        "delete_data",
        "modify_firewall",
        "change_credentials",
        "modify_database_records",
        "disable_security",
    }

    def evaluate(self, action: str, *, service_id: str | None = None) -> PolicyResult:
        if action == "restart_stateless_service" and service_id == "database":
            return PolicyResult(PolicyDecision.ESCALATE, "Database restarts require operator approval")
        if action in self.allowed:
            return PolicyResult(PolicyDecision.ALLOW, "Action is within the automatic policy scope")
        if action in self.forbidden:
            return PolicyResult(PolicyDecision.ESCALATE, "Irreversible or security-sensitive action")
        return PolicyResult(PolicyDecision.ESCALATE, "Unknown actions default to escalation")

    def enforce(self, action: str, *, service_id: str | None = None) -> None:
        result = self.evaluate(action, service_id=service_id)
        if result.decision != PolicyDecision.ALLOW:
            raise PermissionError(result.reason)
