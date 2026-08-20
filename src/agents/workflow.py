from datetime import datetime, timezone
from typing import Dict, Any, Optional

from langgraph.graph import StateGraph, END

from src.agents.state import AgentWorkflowState
from src.agents.research_agent import research_agent_node
from src.agents.writing_agent import writing_agent_node
from src.logger.structured_logger import log_agent_activity


def create_agent_graph():
    """Constructs the compiled LangGraph StateGraph for the multi-agent workflow."""
    workflow = StateGraph(AgentWorkflowState)

    # Register nodes
    workflow.add_node("research", research_agent_node)
    workflow.add_node("writing", writing_agent_node)

    # Define edges
    workflow.set_entry_point("research")
    workflow.add_edge("research", "writing")
    workflow.add_edge("writing", END)

    return workflow.compile()


# Compiled singleton graph
agent_graph = create_agent_graph()


def run_phase1_workflow(task_id: str, prompt: str) -> Dict[str, Any]:
    """
    Executes Phase 1: ResearchAgent -> WritingAgent -> Pause for Approval.
    Returns the updated state containing draft summary and agent audit logs.
    """
    initial_state: AgentWorkflowState = {
        "task_id": task_id,
        "prompt": prompt,
        "research_data": None,
        "draft_summary": None,
        "approved": False,
        "feedback": None,
        "agent_logs": [],
        "status": "RUNNING",
        "error": None,
    }

    final_state = agent_graph.invoke(initial_state)
    return final_state


def run_phase2_workflow(
    task_id: str,
    prompt: str,
    draft_summary: str,
    feedback: Optional[str] = None,
    agent_logs: Optional[list] = None,
) -> Dict[str, Any]:
    """
    Executes Phase 2: Resume upon human approval, finalize summary, and mark completion.
    """
    current_logs = list(agent_logs or [])

    log_agent_activity(
        task_id=task_id,
        agent_name="SupervisorAgent",
        action_details=f"Human approval received. Feedback: '{feedback or 'Approved without extra notes'}'",
    )

    final_result = draft_summary
    if feedback and feedback.strip() and feedback != "Looks good to proceed.":
        final_result = f"{draft_summary}\n\n*Reviewer Feedback Incorporated*: {feedback}"

    log_agent_activity(
        task_id=task_id,
        agent_name="SupervisorAgent",
        action_details="Finalized workflow execution and saved completed result.",
    )

    return {
        "task_id": task_id,
        "result": final_result,
        "agent_logs": current_logs,
        "status": "COMPLETED",
    }
