from __future__ import annotations

from abc import ABC, abstractmethod
from threading import RLock

from app.models import AgentEvent, Incident, utcnow


class Repository(ABC):
    @abstractmethod
    def save_incident(self, incident: Incident) -> Incident: ...

    @abstractmethod
    def get_incident(self, incident_id: str) -> Incident | None: ...

    @abstractmethod
    def list_incidents(self) -> list[Incident]: ...

    @abstractmethod
    def append_event(self, event: AgentEvent) -> AgentEvent: ...

    @abstractmethod
    def list_events(self, incident_id: str) -> list[AgentEvent]: ...

    @abstractmethod
    def clear(self) -> None: ...


class MemoryRepository(Repository):
    def __init__(self) -> None:
        self._incidents: dict[str, Incident] = {}
        self._events: dict[str, list[AgentEvent]] = {}
        self._lock = RLock()

    def save_incident(self, incident: Incident) -> Incident:
        with self._lock:
            incident.updated_at = utcnow()
            self._incidents[incident.id] = incident.model_copy(deep=True)
            return incident.model_copy(deep=True)

    def get_incident(self, incident_id: str) -> Incident | None:
        with self._lock:
            incident = self._incidents.get(incident_id)
            return incident.model_copy(deep=True) if incident else None

    def list_incidents(self) -> list[Incident]:
        with self._lock:
            return sorted(
                (item.model_copy(deep=True) for item in self._incidents.values()),
                key=lambda item: item.created_at,
                reverse=True,
            )

    def append_event(self, event: AgentEvent) -> AgentEvent:
        with self._lock:
            self._events.setdefault(event.incident_id, []).append(event.model_copy(deep=True))
            return event

    def list_events(self, incident_id: str) -> list[AgentEvent]:
        with self._lock:
            return [event.model_copy(deep=True) for event in self._events.get(incident_id, [])]

    def clear(self) -> None:
        with self._lock:
            self._incidents.clear()
            self._events.clear()


class FirestoreRepository(Repository):
    def __init__(self, project: str, database: str = "(default)") -> None:
        from google.cloud import firestore

        self.client = firestore.Client(project=project, database=database)

    def save_incident(self, incident: Incident) -> Incident:
        incident.updated_at = utcnow()
        self.client.collection("incidents").document(incident.id).set(
            incident.model_dump(mode="json")
        )
        return incident

    def get_incident(self, incident_id: str) -> Incident | None:
        snapshot = self.client.collection("incidents").document(incident_id).get()
        return Incident.model_validate(snapshot.to_dict()) if snapshot.exists else None

    def list_incidents(self) -> list[Incident]:
        query = self.client.collection("incidents").order_by(
            "created_at", direction="DESCENDING"
        )
        return [Incident.model_validate(item.to_dict()) for item in query.stream()]

    def append_event(self, event: AgentEvent) -> AgentEvent:
        self.client.collection("agent_events").document(event.id).set(event.model_dump(mode="json"))
        return event

    def list_events(self, incident_id: str) -> list[AgentEvent]:
        query = (
            self.client.collection("agent_events")
            .where("incident_id", "==", incident_id)
            .order_by("timestamp")
        )
        return [AgentEvent.model_validate(item.to_dict()) for item in query.stream()]

    def clear(self) -> None:
        raise RuntimeError("Production Firestore data cannot be cleared through the demo endpoint")

