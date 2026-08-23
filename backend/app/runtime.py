from dataclasses import dataclass

from app.agent import AdkAgentRuntime, AgentRuntime, LocalRuleAgent
from app.config import Settings, get_settings
from app.events import PubSubPublisher
from app.policy import ActionPolicy
from app.repository import FirestoreRepository, MemoryRepository, Repository
from app.simulator import Simulator


@dataclass
class Runtime:
    settings: Settings
    simulator: Simulator
    repository: Repository
    policy: ActionPolicy
    agent: AgentRuntime
    publisher: PubSubPublisher | None = None


def build_runtime(settings: Settings | None = None) -> Runtime:
    settings = settings or get_settings()
    simulator = Simulator()
    policy = ActionPolicy()
    if settings.persistence_backend == "firestore":
        if not settings.google_cloud_project:
            raise ValueError("GOOGLE_CLOUD_PROJECT is required for Firestore")
        repository: Repository = FirestoreRepository(
            settings.google_cloud_project, settings.firestore_database
        )
    else:
        repository = MemoryRepository()
    if settings.agent_runtime == "adk":
        agent: AgentRuntime = AdkAgentRuntime(
            simulator, repository, policy, settings.gemini_model
        )
    else:
        agent = LocalRuleAgent(simulator, repository, policy)
    publisher = None
    if settings.event_backend == "pubsub":
        if not settings.google_cloud_project:
            raise ValueError("GOOGLE_CLOUD_PROJECT is required for Pub/Sub")
        publisher = PubSubPublisher(settings.google_cloud_project, settings.pubsub_topic)
    return Runtime(settings, simulator, repository, policy, agent, publisher)
