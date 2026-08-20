import json
import logging
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from src.db.models import Task
from src.db.session import AsyncSessionLocal
from src.redis_client.client import redis_client

logger = logging.getLogger(__name__)
ws_router = APIRouter()


@ws_router.websocket("/ws/tasks/{task_id}")
async def websocket_task_endpoint(websocket: WebSocket, task_id: str):
    """
    WebSocket endpoint streaming real-time status updates for a specific task.
    Sends current task status upon connection, then streams Redis Pub/Sub status events.
    """
    await websocket.accept()
    logger.info(f"WebSocket client connected for task {task_id}")

    try:
        # Check current status from DB and send initial state if task exists
        async with AsyncSessionLocal() as db:
            try:
                task_uuid = uuid.UUID(task_id)
                stmt = select(Task).where(Task.id == task_uuid)
                result = await db.execute(stmt)
                task = result.scalar_one_or_none()
                if task:
                    await websocket.send_json({"task_id": str(task.id), "status": task.status})
            except Exception:
                pass

        async for raw_message in redis_client.subscribe_status_async(task_id):
            try:
                payload = json.loads(raw_message) if isinstance(raw_message, str) else raw_message
                await websocket.send_json(payload)
                
                # If terminal state reached, break
                if isinstance(payload, dict) and payload.get("status") in ["COMPLETED", "FAILED", "REJECTED"]:
                    break
            except Exception as send_err:
                logger.warning(f"Error sending WebSocket message: {send_err}")
                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected for task {task_id}")
    except Exception as e:
        logger.error(f"WebSocket connection error for task {task_id}: {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
