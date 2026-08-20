from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


class TaskCreateRequest(BaseModel):
    prompt: str = Field(..., description="The initial prompt for the agent workflow", min_length=1)


class TaskCreateResponse(BaseModel):
    task_id: str
    status: str = "PENDING"


class AgentLogEntry(BaseModel):
    agent: str
    action: str
    timestamp: str


class TaskResponse(BaseModel):
    id: str
    prompt: str
    status: str
    result: Optional[str] = None
    agent_logs: Optional[List[Dict[str, Any]]] = None
    created_at: str
    updated_at: str


class TaskApproveRequest(BaseModel):
    approved: bool = True
    feedback: Optional[str] = "Looks good to proceed."


class TaskApproveResponse(BaseModel):
    task_id: str
    status: str = "RESUMED"


class WebSocketTaskUpdate(BaseModel):
    task_id: str
    status: str
