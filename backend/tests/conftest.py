import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.runtime import build_runtime


@pytest.fixture
def runtime():
    return build_runtime(Settings(environment="test", agent_runtime="local"))


@pytest.fixture
def client(runtime):
    with TestClient(app) as value:
        app.state.runtime = runtime
        yield value

