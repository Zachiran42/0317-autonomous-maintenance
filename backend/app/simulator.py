from __future__ import annotations

from copy import deepcopy
from enum import StrEnum
from threading import RLock
from typing import Any

from app.models import HealthState, InfrastructureNode, NodeState


class SimulatorScenario(StrEnum):
    GOLDEN = "golden"
    DEGRADED_PREFLIGHT = "degraded-preflight"


class Simulator:
    """Stateful synthetic production topology with deterministic fault injection."""

    def __init__(self) -> None:
        self._lock = RLock()
        self.reset()

    def reset(self, scenario: SimulatorScenario | str = SimulatorScenario.GOLDEN) -> None:
        with self._lock:
            self.scenario = SimulatorScenario(scenario)
            self._nodes = {
                "load-balancer": InfrastructureNode(
                    id="load-balancer",
                    name="Load Balancer",
                    kind="load_balancer",
                    version="2.3.0",
                    desired_version="2.3.0",
                    capacity_units=100,
                    dependencies=["web01", "web02"],
                ),
                "web01": InfrastructureNode(
                    id="web01",
                    name="WEB01",
                    kind="web",
                    dependencies=["worker", "database"],
                    logs=["INFO web01 serving traffic normally"],
                ),
                "web02": InfrastructureNode(
                    id="web02",
                    name="WEB02",
                    kind="web",
                    dependencies=["worker", "database"],
                    logs=["INFO web02 serving traffic normally"],
                    injected_fault="configuration_incompatible_after_update",
                ),
                "worker": InfrastructureNode(
                    id="worker",
                    name="API / Worker",
                    kind="worker",
                    version="4.2.1",
                    desired_version="4.2.1",
                    in_load_balancer=False,
                    dependencies=["database"],
                ),
                "database": InfrastructureNode(
                    id="database",
                    name="Database",
                    kind="database",
                    version="15.4",
                    desired_version="15.5",
                    in_load_balancer=False,
                    latency_ms=18,
                    capacity_units=100,
                ),
            }
            self._rollback_points: dict[tuple[str, str], dict[str, Any]] = {}
            self._snapshots: dict[str, dict[str, Any]] = {
                "baseline": {"target": "database", "verified": True, "age_minutes": 18}
            }
            if self.scenario == SimulatorScenario.DEGRADED_PREFLIGHT:
                web01 = self._nodes["web01"]
                web01.health = HealthState.DEGRADED
                web01.error_rate = 8.0
                web01.latency_ms = 410
                web01.logs.append("WARN pre-flight health degraded before maintenance")

    def list_nodes(self) -> list[InfrastructureNode]:
        with self._lock:
            return [deepcopy(node) for node in self._nodes.values()]

    def get(self, node_id: str) -> InfrastructureNode:
        with self._lock:
            if node_id not in self._nodes:
                raise KeyError(f"Unknown infrastructure node: {node_id}")
            return deepcopy(self._nodes[node_id])

    def topology(self) -> dict[str, Any]:
        with self._lock:
            return {
                "nodes": [node.model_dump(mode="json") for node in self._nodes.values()],
                "edges": [
                    {"source": "load-balancer", "target": "web01"},
                    {"source": "load-balancer", "target": "web02"},
                    {"source": "web01", "target": "worker"},
                    {"source": "web02", "target": "worker"},
                    {"source": "worker", "target": "database"},
                ],
            }

    def global_error_rate(self) -> float:
        with self._lock:
            active = [
                self._nodes[node]
                for node in ("web01", "web02")
                if self._nodes[node].in_load_balancer
            ]
            return round(sum(node.error_rate for node in active) / max(len(active), 1), 3)

    def check_application_availability(self) -> dict[str, Any]:
        """Measure availability from serving health instead of trusting workflow state."""
        with self._lock:
            serving = [
                self._nodes[node]
                for node in ("web01", "web02")
                if self._nodes[node].in_load_balancer
                and self._nodes[node].health == HealthState.HEALTHY
            ]
            required = 1
            error_rate = self.global_error_rate()
            return {
                "available": len(serving) >= required and error_rate <= 5.0,
                "healthy_serving_web_nodes": len(serving),
                "required_serving_web_nodes": required,
                "serving_targets": [node.id for node in serving],
                "global_error_rate": error_rate,
            }

    def check_capacity(self, excluding: str | None = None) -> dict[str, Any]:
        with self._lock:
            active = [
                self._nodes[node]
                for node in ("web01", "web02")
                if node != excluding
                and self._nodes[node].in_load_balancer
                and self._nodes[node].health == HealthState.HEALTHY
            ]
            capacity = sum(node.capacity_units for node in active)
            return {
                "available_capacity": capacity,
                "required_capacity": 50,
                "passed": capacity >= 50,
            }

    def latest_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._snapshots["baseline"])

    def create_snapshot(self, maintenance_id: str) -> dict[str, Any]:
        with self._lock:
            key = f"snapshot-{maintenance_id}"
            self._snapshots[key] = {
                "id": key,
                "target": "database",
                "verified": True,
                "age_minutes": 0,
                "version": self._nodes["database"].version,
            }
            return deepcopy(self._snapshots[key])

    def drain_node(self, node_id: str) -> InfrastructureNode:
        with self._lock:
            node = self._nodes[node_id]
            if node.kind != "web":
                raise ValueError("Only web nodes can be drained")
            node.state = NodeState.DRAINING
            node.in_load_balancer = False
            node.logs.append("INFO node drained from load balancer")
            return deepcopy(node)

    def create_rollback_point(self, maintenance_id: str, node_id: str) -> dict[str, Any]:
        with self._lock:
            node = self._nodes[node_id]
            key = (maintenance_id, node_id)
            self._rollback_points[key] = {
                "maintenance_id": maintenance_id,
                "target": node_id,
                "version": node.version,
                "health": node.health,
                "error_rate": node.error_rate,
                "latency_ms": node.latency_ms,
                "verified": True,
            }
            return deepcopy(self._rollback_points[key])

    def has_rollback_point(self, maintenance_id: str, node_id: str) -> bool:
        with self._lock:
            return (maintenance_id, node_id) in self._rollback_points

    def apply_maintenance(self, maintenance_id: str, node_id: str) -> InfrastructureNode:
        with self._lock:
            node = self._nodes[node_id]
            if node.kind != "web" or node.in_load_balancer:
                raise ValueError("Web maintenance requires a drained node")
            node.state = NodeState.MAINTENANCE
            node.active_change_id = maintenance_id
            node.version = node.desired_version
            node.logs.append(f"INFO applied approved update {node.desired_version}")
            return deepcopy(node)

    def restart_service(self, node_id: str) -> InfrastructureNode:
        with self._lock:
            node = self._nodes[node_id]
            node.state = NodeState.STARTING
            node.logs.append("INFO service restarted; readiness probe pending")
            return deepcopy(node)

    def run_health_check(self, node_id: str) -> dict[str, Any]:
        with self._lock:
            node = self._nodes[node_id]
            node.state = NodeState.VERIFYING
            node.health = HealthState.HEALTHY
            node.latency_ms = 52
            return {
                "target": node_id,
                "passed": True,
                "health": node.health,
                "latency_ms": node.latency_ms,
            }

    def run_synthetic_test(self, node_id: str) -> dict[str, Any]:
        with self._lock:
            node = self._nodes[node_id]
            if node.injected_fault and node.active_change_id:
                node.health = HealthState.DEGRADED
                node.error_rate = 24.0
                node.latency_ms = 780
                node.logs.extend(
                    [
                        "ERROR synthetic checkout returned HTTP 500",
                        "ERROR updated configuration incompatible with worker protocol",
                    ]
                )
                return {
                    "target": node_id,
                    "passed": False,
                    "error_rate": node.error_rate,
                    "threshold": 5.0,
                    "reason": "Functional verification failed after update",
                }
            node.health = HealthState.HEALTHY
            node.error_rate = 0.2
            node.latency_ms = 47
            return {
                "target": node_id,
                "passed": True,
                "error_rate": node.error_rate,
                "threshold": 5.0,
            }

    def restore_node_to_pool(self, node_id: str) -> InfrastructureNode:
        with self._lock:
            node = self._nodes[node_id]
            if node.health != HealthState.HEALTHY:
                raise RuntimeError("Unhealthy node cannot return to the load balancer")
            node.in_load_balancer = True
            node.state = NodeState.HEALTHY
            node.active_change_id = None
            node.logs.append("INFO node restored to load balancer")
            return deepcopy(node)

    def rollback_change(self, maintenance_id: str, node_id: str) -> InfrastructureNode:
        with self._lock:
            key = (maintenance_id, node_id)
            if key not in self._rollback_points:
                raise RuntimeError("No eligible rollback point")
            node = self._nodes[node_id]
            if node.active_change_id != maintenance_id:
                raise PermissionError("Rollback can only revert the current maintenance change")
            snapshot = self._rollback_points[key]
            node.version = snapshot["version"]
            node.health = HealthState.HEALTHY
            node.error_rate = snapshot["error_rate"]
            node.latency_ms = snapshot["latency_ms"]
            node.in_load_balancer = True
            node.state = NodeState.ROLLED_BACK
            node.active_change_id = None
            node.logs.append("WARN failed update rolled back and previous configuration restored")
            return deepcopy(node)

    def verify_rollback(self, maintenance_id: str, node_id: str) -> dict[str, Any]:
        with self._lock:
            snapshot = self._rollback_points.get((maintenance_id, node_id))
            node = self._nodes[node_id]
            passed = bool(
                snapshot
                and node.version == snapshot["version"]
                and node.health == HealthState.HEALTHY
                and node.in_load_balancer
            )
            return {
                "target": node_id,
                "passed": passed,
                "version": node.version,
                "health": node.health,
                "in_load_balancer": node.in_load_balancer,
            }

    def apply_database_maintenance(self, maintenance_id: str) -> InfrastructureNode:
        with self._lock:
            snapshot = self._snapshots.get(f"snapshot-{maintenance_id}")
            if not snapshot or not snapshot["verified"]:
                raise RuntimeError("Database maintenance requires a verified owned snapshot")
            node = self._nodes["database"]
            node.state = NodeState.MAINTENANCE
            node.version = node.desired_version
            node.state = NodeState.HEALTHY
            node.logs.append("INFO approved database maintenance completed")
            return deepcopy(node)
