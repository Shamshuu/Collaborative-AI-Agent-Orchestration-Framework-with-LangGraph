import pytest
import json
import asyncio
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from src.main import app


def test_websocket_streaming():
    """Test that WebSocket /ws/tasks/{task_id} accepts connection and receives messages."""
    client = TestClient(app)
    task_id = "test-ws-task-123"

    async def mock_subscribe(task_id):
        yield json.dumps({"task_id": task_id, "status": "RUNNING"})
        yield json.dumps({"task_id": task_id, "status": "AWAITING_APPROVAL"})
        yield json.dumps({"task_id": task_id, "status": "COMPLETED"})

    with patch("src.api.websockets.redis_client.subscribe_status_async", side_effect=mock_subscribe):
        with client.websocket_connect(f"/ws/tasks/{task_id}") as websocket:
            msg1 = websocket.receive_json()
            assert msg1 == {"task_id": task_id, "status": "RUNNING"}

            msg2 = websocket.receive_json()
            assert msg2 == {"task_id": task_id, "status": "AWAITING_APPROVAL"}

            msg3 = websocket.receive_json()
            assert msg3 == {"task_id": task_id, "status": "COMPLETED"}
