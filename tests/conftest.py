import pytest
import os
import uuid
from unittest.mock import MagicMock, patch, AsyncMock
from httpx import AsyncClient, ASGITransport

from src.main import app
from src.config.settings import settings
from src.redis_client.client import redis_client


@pytest.fixture(autouse=True)
def setup_test_env():
    """Ensure test log directory exists and reset flaky tool."""
    from src.agents.tools import reset_flaky_attempts
    reset_flaky_attempts()
    os.makedirs("logs", exist_ok=True)
    yield


@pytest.fixture
def sample_task_id():
    return str(uuid.uuid4())


@pytest.fixture
def mock_redis():
    """Mock Redis client for unit testing."""
    scratchpad = {}

    def mock_save_sync(task_id, data, ttl=86400):
        scratchpad[f"task:{task_id}:workspace"] = data

    def mock_get_sync(task_id):
        return scratchpad.get(f"task:{task_id}:workspace")

    async def mock_save_async(task_id, data, ttl=86400):
        scratchpad[f"task:{task_id}:workspace"] = data

    async def mock_get_async(task_id):
        return scratchpad.get(f"task:{task_id}:workspace")

    with patch.object(redis_client, "save_workspace_sync", side_effect=mock_save_sync), \
         patch.object(redis_client, "get_workspace_sync", side_effect=mock_get_sync), \
         patch.object(redis_client, "save_workspace_async", side_effect=mock_save_async), \
         patch.object(redis_client, "get_workspace_async", side_effect=mock_get_async), \
         patch.object(redis_client, "publish_status_sync") as mock_pub_sync, \
         patch.object(redis_client, "publish_status_async") as mock_pub_async:
        yield {
            "scratchpad": scratchpad,
            "save_sync": mock_save_sync,
            "get_sync": mock_get_sync,
            "pub_sync": mock_pub_sync,
            "pub_async": mock_pub_async,
        }
