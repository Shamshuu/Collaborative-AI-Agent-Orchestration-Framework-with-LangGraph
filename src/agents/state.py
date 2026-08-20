from typing import TypedDict, List, Dict, Any, Optional


class AgentWorkflowState(TypedDict):
    task_id: str
    prompt: str
    research_data: Optional[Any]
    draft_summary: Optional[str]
    approved: bool
    feedback: Optional[str]
    agent_logs: List[Dict[str, Any]]
    status: str
    error: Optional[str]
