import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.db.models import Task
from src.db.schemas import (
    TaskCreateRequest,
    TaskCreateResponse,
    TaskResponse,
    TaskApproveRequest,
    TaskApproveResponse,
)
from src.db.session import get_async_db
from src.redis_client.client import redis_client
from src.worker.tasks import run_agent_workflow, resume_agent_workflow

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=TaskCreateResponse)
async def create_task(
    request: TaskCreateRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Initiate a new collaborative agent task.
    Saves task in database with status PENDING and queues Celery background worker.
    """
    task_id = uuid.uuid4()
    new_task = Task(
        id=task_id,
        prompt=request.prompt,
        status="PENDING",
        result=None,
        agent_logs=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)

    # Trigger Celery background task
    run_agent_workflow.delay(str(task_id), request.prompt)

    return TaskCreateResponse(task_id=str(task_id), status="PENDING")


@router.get("/{task_id}", status_code=status.HTTP_200_OK, response_model=TaskResponse)
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Retrieve the current status and details of a specific task by its UUID.
    """
    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task UUID format")

    stmt = select(Task).where(Task.id == task_uuid)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskResponse(
        id=str(task.id),
        prompt=task.prompt,
        status=task.status,
        result=task.result,
        agent_logs=task.agent_logs,
        created_at=task.created_at.isoformat() if task.created_at else "",
        updated_at=task.updated_at.isoformat() if task.updated_at else "",
    )


@router.post("/{task_id}/approve", status_code=status.HTTP_200_OK, response_model=TaskApproveResponse)
async def approve_task(
    task_id: str,
    request: TaskApproveRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Provide human approval for a task paused at the AWAITING_APPROVAL decision point.
    Updates status to RESUMED and triggers the completion workflow.
    """
    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task UUID format")

    stmt = select(Task).where(Task.id == task_uuid)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status not in ["AWAITING_APPROVAL", "RUNNING"]:
        raise HTTPException(
            status_code=400,
            detail=f"Task cannot be approved in its current status: '{task.status}'",
        )

    if not request.approved:
        task.status = "REJECTED"
        task.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await redis_client.publish_status_async(task_id, "REJECTED")
        return TaskApproveResponse(task_id=str(task.id), status="REJECTED")

    # Update status to RESUMED
    task.status = "RESUMED"
    task.updated_at = datetime.now(timezone.utc)
    await db.commit()

    # Publish RESUMED event
    await redis_client.publish_status_async(task_id, "RESUMED")

    # Resume workflow in background Celery worker
    resume_agent_workflow.delay(str(task_id), request.feedback)

    return TaskApproveResponse(task_id=str(task.id), status="RESUMED")
