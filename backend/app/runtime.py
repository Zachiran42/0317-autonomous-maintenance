from dataclasses import dataclass

from app.agent import AdkPlanner, LocalPlanner, MaintenanceAgent, SafeMaintenanceAgent
from app.config import Settings, get_settings
from app.events import PubSubPublisher
from app.policy import EvidenceGate
from app.repository import FirestoreRepository, MemoryRepository, Repository
from app.simulator import Simulator


@dataclass
class Runtime:
    settings: Settings
    simulator: Simulator
    repository: Repository
    gate: EvidenceGate
    agent: MaintenanceAgent
    publisher: PubSubPublisher | None = None


def build_runtime(settings: Settings | None = None) -> Runtime:
    settings = settings or get_settings()
    simulator = Simulator()
    gate = EvidenceGate(simulator)
    if settings.persistence_backend == "firestore":
        if not settings.google_cloud_project:
            raise ValueError("GOOGLE_CLOUD_PROJECT is required for Firestore")
        repository: Repository = FirestoreRepository(
            settings.google_cloud_project, settings.firestore_database
        )
    else:
        repository = MemoryRepository()
    planner = (
        AdkPlanner(settings.gemini_model)
        if settings.agent_runtime == "adk"
        else LocalPlanner()
    )
    agent = SafeMaintenanceAgent(
        simulator, repository, gate, planner, settings.demo_step_delay_seconds
    )
    publisher = None
    if settings.event_backend == "pubsub":
        if not settings.google_cloud_project:
            raise ValueError("GOOGLE_CLOUD_PROJECT is required for Pub/Sub")
        publisher = PubSubPublisher(settings.google_cloud_project, settings.pubsub_topic)
    return Runtime(settings, simulator, repository, gate, agent, publisher)
