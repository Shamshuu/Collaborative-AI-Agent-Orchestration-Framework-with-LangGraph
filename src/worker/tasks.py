import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from src.agents.workflow import run_phase1_workflow, run_phase2_workflow
from src.db.models import Task
from src.db.session import get_sync_db
from src.logger.structured_logger import log_agent_activity
from src.redis_client.client import redis_client
from src.worker.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(name="src.worker.tasks.run_agent_workflow", bind=True)
def run_agent_workflow(self, task_id: str, prompt: str):
    """
    Celery task to execute Phase 1 of the multi-agent workflow:
    1. Mark status as RUNNING in DB and publish status.
    2. Run LangGraph Phase 1 (ResearchAgent -> WritingAgent).
    3. Update DB to AWAITING_APPROVAL, save draft and agent_logs.
    4. Publish AWAITING_APPROVAL status to WebSocket channel.
    """
    task_uuid = uuid.UUID(task_id)

    # 1. Update task to RUNNING in database
    with get_sync_db() as db:
        task = db.query(Task).filter(Task.id == task_uuid).first()
        if task:
            task.status = "RUNNING"
            task.updated_at = datetime.now(timezone.utc)
            db.commit()

    # Publish RUNNING status update
    redis_client.publish_status_sync(task_id, "RUNNING")
    log_agent_activity(
        task_id=task_id,
        agent_name="SupervisorAgent",
        action_details="Transitioned task status to RUNNING and dispatched LangGraph Phase 1 execution.",
    )

    try:
        # 2. Run LangGraph Phase 1
        phase1_state = run_phase1_workflow(task_id=task_id, prompt=prompt)
        draft = phase1_state.get("draft_summary")
        agent_logs = phase1_state.get("agent_logs", [])

        # 3. Update task to AWAITING_APPROVAL
        with get_sync_db() as db:
            task = db.query(Task).filter(Task.id == task_uuid).first()
            if task:
                task.status = "AWAITING_APPROVAL"
                task.result = draft
                task.agent_logs = agent_logs
                task.updated_at = datetime.now(timezone.utc)
                db.commit()

        # 4. Publish AWAITING_APPROVAL status update
        redis_client.publish_status_sync(task_id, "AWAITING_APPROVAL")
        log_agent_activity(
            task_id=task_id,
            agent_name="SupervisorAgent",
            action_details="Phase 1 complete. Pausing workflow execution for human approval (status: AWAITING_APPROVAL).",
        )
        return {"status": "AWAITING_APPROVAL", "task_id": task_id}

    except Exception as e:
        logger.exception("Error during agent workflow execution")
        log_agent_activity(
            task_id=task_id,
            agent_name="SupervisorAgent",
            action_details=f"Workflow failed with error: {str(e)}",
        )
        with get_sync_db() as db:
            task = db.query(Task).filter(Task.id == task_uuid).first()
            if task:
                task.status = "FAILED"
                task.result = f"Execution error: {str(e)}"
                task.updated_at = datetime.now(timezone.utc)
                db.commit()

        redis_client.publish_status_sync(task_id, "FAILED")
        raise


@celery.task(name="src.worker.tasks.resume_agent_workflow", bind=True)
def resume_agent_workflow(self, task_id: str, feedback: Optional[str] = None):
    """
    Celery task to execute Phase 2 after human approval:
    1. Mark status as RUNNING in DB and publish status.
    2. Finalize summary with human feedback.
    3. Update DB to COMPLETED, save final result and logs.
    4. Publish COMPLETED status to WebSocket channel.
    """
    task_uuid = uuid.UUID(task_id)

    # 1. Fetch current draft and logs from DB
    draft = None
    prompt = ""
    agent_logs = []
    with get_sync_db() as db:
        task = db.query(Task).filter(Task.id == task_uuid).first()
        if task:
            draft = task.result or ""
            prompt = task.prompt
            agent_logs = list(task.agent_logs or [])
            task.status = "RUNNING"
            task.updated_at = datetime.now(timezone.utc)
            db.commit()

    redis_client.publish_status_sync(task_id, "RUNNING")
    log_agent_activity(
        task_id=task_id,
        agent_name="SupervisorAgent",
        action_details="Workflow resumed from checkpoint after human approval.",
    )

    try:
        # 2. Finalize workflow
        phase2_result = run_phase2_workflow(
            task_id=task_id,
            prompt=prompt,
            draft_summary=draft,
            feedback=feedback,
            agent_logs=agent_logs,
        )

        final_result = phase2_result["result"]
        final_logs = phase2_result["agent_logs"]

        # 3. Update DB to COMPLETED
        with get_sync_db() as db:
            task = db.query(Task).filter(Task.id == task_uuid).first()
            if task:
                task.status = "COMPLETED"
                task.result = final_result
                task.agent_logs = final_logs
                task.updated_at = datetime.now(timezone.utc)
                db.commit()

        # 4. Publish COMPLETED status update
        redis_client.publish_status_sync(task_id, "COMPLETED")
        log_agent_activity(
            task_id=task_id,
            agent_name="SupervisorAgent",
            action_details="Workflow completed successfully (status: COMPLETED).",
        )
        return {"status": "COMPLETED", "task_id": task_id}

    except Exception as e:
        logger.exception("Error during agent workflow resumption")
        log_agent_activity(
            task_id=task_id,
            agent_name="SupervisorAgent",
            action_details=f"Workflow resumption failed with error: {str(e)}",
        )
        with get_sync_db() as db:
            task = db.query(Task).filter(Task.id == task_uuid).first()
            if task:
                task.status = "FAILED"
                task.result = f"Resumption error: {str(e)}"
                task.updated_at = datetime.now(timezone.utc)
                db.commit()

        redis_client.publish_status_sync(task_id, "FAILED")
        raise
