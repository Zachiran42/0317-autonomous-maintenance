from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["local", "production", "test"] = "local"
    agent_runtime: Literal["local", "adk"] = "local"
    persistence_backend: Literal["memory", "firestore"] = "memory"
    event_backend: Literal["local", "pubsub"] = "local"
    google_cloud_project: str | None = None
    google_cloud_location: str = "global"
    gemini_model: str = "gemini-3.5-flash"
    firestore_database: str = "(default)"
    pubsub_topic: str = "maintenance-events"
    pubsub_subscription: str = "maintenance-worker"
    demo_step_delay_seconds: float = 0.0
    cors_origins: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
