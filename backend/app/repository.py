from __future__ import annotations

from abc import ABC, abstractmethod
from threading import RLock

from app.models import ActionExecution, MaintenanceEvent, MaintenanceRun, utcnow


class Repository(ABC):
    @abstractmethod
    def save_run(self, run: MaintenanceRun) -> MaintenanceRun: ...

    @abstractmethod
    def get_run(self, maintenance_id: str) -> MaintenanceRun | None: ...

    @abstractmethod
    def list_runs(self) -> list[MaintenanceRun]: ...

    @abstractmethod
    def append_event(self, event: MaintenanceEvent) -> MaintenanceEvent: ...

    @abstractmethod
    def list_events(self, maintenance_id: str) -> list[MaintenanceEvent]: ...

    @abstractmethod
    def save_action(self, action: ActionExecution) -> ActionExecution: ...

    @abstractmethod
    def get_action_by_key(self, idempotency_key: str) -> ActionExecution | None: ...

    @abstractmethod
    def clear(self) -> None: ...


class MemoryRepository(Repository):
    def __init__(self) -> None:
        self._runs: dict[str, MaintenanceRun] = {}
        self._events: dict[str, list[MaintenanceEvent]] = {}
        self._actions: dict[str, ActionExecution] = {}
        self._lock = RLock()

    def save_run(self, run: MaintenanceRun) -> MaintenanceRun:
        with self._lock:
            run.updated_at = utcnow()
            self._runs[run.id] = run.model_copy(deep=True)
            return run.model_copy(deep=True)

    def get_run(self, maintenance_id: str) -> MaintenanceRun | None:
        with self._lock:
            run = self._runs.get(maintenance_id)
            return run.model_copy(deep=True) if run else None

    def list_runs(self) -> list[MaintenanceRun]:
        with self._lock:
            return sorted(
                (run.model_copy(deep=True) for run in self._runs.values()),
                key=lambda run: run.created_at,
                reverse=True,
            )

    def append_event(self, event: MaintenanceEvent) -> MaintenanceEvent:
        with self._lock:
            self._events.setdefault(event.maintenance_id, []).append(event.model_copy(deep=True))
            return event.model_copy(deep=True)

    def list_events(self, maintenance_id: str) -> list[MaintenanceEvent]:
        with self._lock:
            return [event.model_copy(deep=True) for event in self._events.get(maintenance_id, [])]

    def save_action(self, action: ActionExecution) -> ActionExecution:
        with self._lock:
            self._actions[action.idempotency_key] = action.model_copy(deep=True)
            return action.model_copy(deep=True)

    def get_action_by_key(self, idempotency_key: str) -> ActionExecution | None:
        with self._lock:
            action = self._actions.get(idempotency_key)
            return action.model_copy(deep=True) if action else None

    def clear(self) -> None:
        with self._lock:
            self._runs.clear()
            self._events.clear()
            self._actions.clear()


class FirestoreRepository(Repository):
    def __init__(self, project: str, database: str = "(default)") -> None:
        from google.cloud import firestore

        self.client = firestore.Client(project=project, database=database)

    def save_run(self, run: MaintenanceRun) -> MaintenanceRun:
        run.updated_at = utcnow()
        self.client.collection("maintenance_runs").document(run.id).set(
            run.model_dump(mode="json")
        )
        return run

    def get_run(self, maintenance_id: str) -> MaintenanceRun | None:
        snapshot = self.client.collection("maintenance_runs").document(maintenance_id).get()
        return MaintenanceRun.model_validate(snapshot.to_dict()) if snapshot.exists else None

    def list_runs(self) -> list[MaintenanceRun]:
        query = self.client.collection("maintenance_runs").order_by(
            "created_at", direction="DESCENDING"
        )
        return [MaintenanceRun.model_validate(item.to_dict()) for item in query.stream()]

    def append_event(self, event: MaintenanceEvent) -> MaintenanceEvent:
        self.client.collection("maintenance_events").document(event.id).set(
            event.model_dump(mode="json")
        )
        return event

    def list_events(self, maintenance_id: str) -> list[MaintenanceEvent]:
        query = (
            self.client.collection("maintenance_events")
            .where("maintenance_id", "==", maintenance_id)
            .order_by("timestamp")
        )
        return [MaintenanceEvent.model_validate(item.to_dict()) for item in query.stream()]

    def save_action(self, action: ActionExecution) -> ActionExecution:
        self.client.collection("action_executions").document(action.idempotency_key).set(
            action.model_dump(mode="json")
        )
        return action

    def get_action_by_key(self, idempotency_key: str) -> ActionExecution | None:
        snapshot = self.client.collection("action_executions").document(idempotency_key).get()
        return ActionExecution.model_validate(snapshot.to_dict()) if snapshot.exists else None

    def clear(self) -> None:
        # Production reset restores simulator state but preserves the immutable audit trail.
        return None

