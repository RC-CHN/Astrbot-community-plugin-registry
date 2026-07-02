import pytest
from fastapi.testclient import TestClient

from astrbot_registry.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
