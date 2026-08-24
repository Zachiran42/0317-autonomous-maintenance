from __future__ import annotations

from enum import StrEnum
from typing import ClassVar

from app.models import EvidenceItem, GateDecision, GateOutcome, HealthState
from app.simulator import Simulator


class ActionCategory(StrEnum):
    READ = "read"
    SAFE_CHANGE = "safe_change"
    ROLLBACK = "rollback"
    RESTRICTED = "restricted"


class EvidenceGate:
    read_actions: ClassVar[set[str]] = {
        "get_change_request",
        "get_topology",
        "get_service_health",
        "get_metrics",
        "get_recent_logs",
        "search_runbooks",
        "search_maintenance_history",
        "check_capacity",
        "check_application_availability",
        "evaluate_evidence",
    }
    safe_actions: ClassVar[set[str]] = {
        "create_snapshot",
        "drain_node",
        "create_rollback_point",
        "apply_maintenance",
        "restart_service",
        "run_health_check",
        "run_synthetic_test",
        "restore_node_to_pool",
        "create_maintenance_report",
        "defer_change",
        "apply_database_maintenance",
    }
    rollback_actions: ClassVar[set[str]] = {"rollback_change", "verify_rollback"}
    restricted_actions: ClassVar[set[str]] = {
        "delete_database",
        "delete_backup",
        "disable_auditing",
        "modify_credentials",
        "disable_security_controls",
        "destructive_schema_change",
        "arbitrary_shell",
    }

    def __init__(self, simulator: Simulator) -> None:
        self.simulator = simulator

    def category(self, action: str) -> ActionCategory:
        if action in self.read_actions:
            return ActionCategory.READ
        if action in self.safe_actions:
            return ActionCategory.SAFE_CHANGE
        if action in self.rollback_actions:
            return ActionCategory.ROLLBACK
        return ActionCategory.RESTRICTED

    def evaluate(
        self, gate: str, target: str, maintenance_id: str, approved: bool = True
    ) -> GateDecision:
        if gate == "maintenance_window":
            nodes = [self.simulator.get(node) for node in ("web01", "web02", "database")]
            capacity = self.simulator.check_capacity()
            snapshot = self.simulator.latest_snapshot()
            evidence = [
                EvidenceItem(
                    key="approved",
                    label="Change request approved",
                    passed=approved,
                    observed=approved,
                    required=True,
                ),
                *[
                    EvidenceItem(
                        key=f"{node.id}_health",
                        label=f"{node.name} health",
                        passed=node.health == HealthState.HEALTHY,
                        observed=node.health,
                        required=HealthState.HEALTHY,
                    )
                    for node in nodes
                ],
                EvidenceItem(
                    key="minimum_capacity",
                    label="Minimum web capacity",
                    passed=capacity["passed"],
                    observed=capacity["available_capacity"],
                    required=capacity["required_capacity"],
                ),
                EvidenceItem(
                    key="backup_available",
                    label="Recent backup available",
                    passed=snapshot["verified"] and snapshot["age_minutes"] < 60,
                    observed=snapshot["age_minutes"],
                    required="verified and < 60 minutes",
                ),
            ]
        elif gate == "drain_node":
            capacity = self.simulator.check_capacity(excluding=target)
            evidence = [
                EvidenceItem(
                    key="remaining_capacity",
                    label="Remaining web capacity",
                    passed=capacity["passed"],
                    observed=capacity["available_capacity"],
                    required=capacity["required_capacity"],
                )
            ]
        elif gate == "apply_web_change":
            node = self.simulator.get(target)
            rollback_exists = self.simulator.has_rollback_point(maintenance_id, target)
            evidence = [
                EvidenceItem(
                    key="node_drained",
                    label="Node drained",
                    passed=not node.in_load_balancer,
                    observed=node.in_load_balancer,
                    required=False,
                ),
                EvidenceItem(
                    key="rollback_point",
                    label="Rollback point verified",
                    passed=rollback_exists,
                    observed=rollback_exists,
                    required=True,
                ),
            ]
        elif gate == "rollback":
            node = self.simulator.get(target)
            rollback_exists = self.simulator.has_rollback_point(maintenance_id, target)
            evidence = [
                EvidenceItem(
                    key="rollback_point",
                    label="Rollback point exists",
                    passed=rollback_exists,
                    observed=rollback_exists,
                    required=True,
                ),
                EvidenceItem(
                    key="change_owner",
                    label="Current maintenance owns change",
                    passed=node.active_change_id == maintenance_id,
                    observed=node.active_change_id,
                    required=maintenance_id,
                ),
            ]
        elif gate == "database_change":
            database = self.simulator.get("database")
            web01 = self.simulator.get("web01")
            web02 = self.simulator.get("web02")
            snapshot = self.simulator.latest_snapshot()
            evidence = [
                EvidenceItem(
                    key="recent_backup",
                    label="Recent backup exists",
                    passed=snapshot["verified"],
                    observed=snapshot["age_minutes"],
                    required="verified",
                ),
                EvidenceItem(
                    key="database_health",
                    label="Database currently healthy",
                    passed=database.health == HealthState.HEALTHY,
                    observed=database.health,
                    required=HealthState.HEALTHY,
                ),
                EvidenceItem(
                    key="web01_target",
                    label="WEB01 desired version healthy",
                    passed=web01.health == HealthState.HEALTHY
                    and web01.version == web01.desired_version,
                    observed=f"{web01.health}/{web01.version}",
                    required=web01.desired_version,
                ),
                EvidenceItem(
                    key="web02_target",
                    label="WEB02 desired version healthy",
                    passed=web02.health == HealthState.HEALTHY
                    and web02.version == web02.desired_version,
                    observed=f"{web02.health}/{web02.version}",
                    required=web02.desired_version,
                ),
                EvidenceItem(
                    key="full_redundancy",
                    label="Web tier fully redundant",
                    passed=web01.in_load_balancer
                    and web02.in_load_balancer
                    and web01.version == web01.desired_version
                    and web02.version == web02.desired_version,
                    observed={"web01": web01.in_load_balancer, "web02": web02.in_load_balancer},
                    required="two healthy target-version nodes",
                ),
                EvidenceItem(
                    key="global_error_rate",
                    label="Global application error rate",
                    passed=self.simulator.global_error_rate() <= 5.0,
                    observed=self.simulator.global_error_rate(),
                    required="<= 5%",
                ),
            ]
        else:
            evidence = [
                EvidenceItem(
                    key="unknown_gate",
                    label="Known evidence gate",
                    passed=False,
                    observed=gate,
                    required="registered gate",
                )
            ]
        passed = all(item.passed for item in evidence)
        return GateDecision(
            gate=gate,
            target=target,
            outcome=GateOutcome.PASS if passed else GateOutcome.FAIL,
            summary=(
                f"{gate} evidence satisfied"
                if passed
                else f"{gate} blocked by unsatisfied evidence"
            ),
            evidence=evidence,
        )

    def enforce_action(self, action: str) -> None:
        if self.category(action) == ActionCategory.RESTRICTED:
            raise PermissionError(f"Restricted or unknown action rejected: {action}")

    def enforce_gate(self, decision: GateDecision) -> None:
        if decision.outcome != GateOutcome.PASS:
            failed = ", ".join(item.label for item in decision.evidence if not item.passed)
            raise PermissionError(f"Evidence Gate rejected {decision.gate}: {failed}")
