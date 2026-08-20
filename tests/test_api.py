import pytest
import uuid
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport

from src.main import app
from src.db.models import Task
from src.db.session import get_async_db


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test GET /health returns 200 OK."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data


@pytest.mark.asyncio
async def test_create_task_endpoint():
    """Test POST /api/v1/tasks returns 202 Accepted and queues background task."""
    transport = ASGITransport(app=app)
    
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_async_db] = override_get_db

    try:
        with patch("src.api.v1.tasks.run_agent_workflow.delay") as mock_delay:
            mock_delay.return_value = MagicMock(id="celery-task-1")
            
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/v1/tasks", json={"prompt": "Test prompt"})
                assert response.status_code == 202
                data = response.json()
                assert "task_id" in data
                assert data["status"] == "PENDING"
                assert mock_delay.called
    finally:
        app.dependency_overrides.pop(get_async_db, None)


@pytest.mark.asyncio
async def test_get_task_endpoint():
    """Test GET /api/v1/tasks/{task_id} returns task data."""
    transport = ASGITransport(app=app)
    task_id = uuid.uuid4()
    
    mock_task = Task(
        id=task_id,
        prompt="Test prompt",
        status="RUNNING",
        result=None,
        agent_logs=[{"agent": "ResearchAgent", "action": "Working", "timestamp": "2026-08-16T12:00:00Z"}],
    )

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_task
    mock_session.execute.return_value = mock_result

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_async_db] = override_get_db

    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/tasks/{task_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == str(task_id)
            assert data["status"] == "RUNNING"
            assert len(data["agent_logs"]) == 1
    finally:
        app.dependency_overrides.pop(get_async_db, None)


@pytest.mark.asyncio
async def test_approve_task_endpoint():
    """Test POST /api/v1/tasks/{task_id}/approve resumes paused task."""
    transport = ASGITransport(app=app)
    task_id = uuid.uuid4()
    
    mock_task = Task(
        id=task_id,
        prompt="Test prompt",
        status="AWAITING_APPROVAL",
        result="Draft summary",
        agent_logs=[],
    )

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_task
    mock_session.execute.return_value = mock_result
    mock_session.commit = AsyncMock()

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_async_db] = override_get_db

    try:
        with patch("src.api.v1.tasks.resume_agent_workflow.delay") as mock_resume, \
             patch("src.api.v1.tasks.redis_client.publish_status_async", new_callable=AsyncMock) as mock_pub:
            
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/tasks/{task_id}/approve",
                    json={"approved": True, "feedback": "Approved!"}
                )
                assert response.status_code == 200
                data = response.json()
                assert data["task_id"] == str(task_id)
                assert data["status"] == "RESUMED"
                assert mock_resume.called
    finally:
        app.dependency_overrides.pop(get_async_db, None)
