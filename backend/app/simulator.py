from copy import deepcopy
from threading import RLock

from app.models import HealthState, Service


class Simulator:
    def __init__(self) -> None:
        self._lock = RLock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self._services = {
                "web-api": Service(id="web-api", name="Web API", dependencies=["database"]),
                "database": Service(id="database", name="Database", latency_ms=18),
                "worker": Service(id="worker", name="Worker", dependencies=["database"]),
            }

    def list_services(self) -> list[Service]:
        with self._lock:
            return [deepcopy(service) for service in self._services.values()]

    def get(self, service_id: str) -> Service:
        with self._lock:
            if service_id not in self._services:
                raise KeyError(f"Unknown service: {service_id}")
            return deepcopy(self._services[service_id])

    def trigger(self, scenario: str) -> Service:
        with self._lock:
            if scenario == "recoverable":
                service = self._services["web-api"]
                service.health = HealthState.UNHEALTHY
                service.cpu_percent = 98
                service.error_rate = 34.7
                service.latency_ms = 4200
                service.fault = "worker_deadlock"
                service.logs = [
                    "ERROR request timeout waiting for worker pool",
                    "WARN worker heartbeat missed for 90s",
                    "ERROR worker pool deadlock detected",
                ]
            elif scenario == "unsafe":
                service = self._services["database"]
                service.health = HealthState.DEGRADED
                service.cpu_percent = 76
                service.error_rate = 12.4
                service.latency_ms = 960
                service.fault = "data_corruption"
                service.logs = [
                    "ERROR checksum mismatch on page 1842",
                    "CRITICAL possible data corruption in customer_index",
                    "WARN replica replay paused to preserve evidence",
                ]
            else:
                raise ValueError(f"Unknown scenario: {scenario}")
            return deepcopy(service)

    def restart(self, service_id: str) -> Service:
        with self._lock:
            service = self._services[service_id]
            if service_id == "database":
                raise RuntimeError("Database restart is not supported by the simulator action tool")
            service.restart_count += 1
            service.health = HealthState.HEALTHY
            service.cpu_percent = 24
            service.memory_percent = 37
            service.error_rate = 0.1
            service.latency_ms = 48
            service.fault = None
            service.logs.append("INFO service restarted and readiness checks passed")
            return deepcopy(service)

