from datetime import datetime, timezone
import time
from typing import Dict, Any

from src.agents.state import AgentWorkflowState
from src.agents.tools import simulated_search_tool
from src.logger.structured_logger import log_agent_activity
from src.redis_client.client import redis_client


def research_agent_node(state: AgentWorkflowState) -> Dict[str, Any]:
    """
    ResearchAgent node:
    - Gathers technical research using search tool with automated retry logic.
    - Persists findings to Redis workspace scratchpad (task:<task_id>:workspace).
    - Logs structured actions to logs/agent_activity.log and agent audit logs.
    """
    task_id = state["task_id"]
    prompt = state["prompt"]
    agent_logs = list(state.get("agent_logs") or [])

    # Structured log: starting action
    log_agent_activity(
        task_id=task_id,
        agent_name="ResearchAgent",
        action_details=f"Starting web search for '{prompt}'",
    )

    # Retry loop for fault tolerance (handles flaky tool)
    max_retries = 3
    research_results = None
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            research_results = simulated_search_tool(prompt)
            if attempt > 1:
                log_agent_activity(
                    task_id=task_id,
                    agent_name="ResearchAgent",
                    action_details=f"Tool execution succeeded on retry attempt {attempt}.",
                )
            break
        except Exception as e:
            last_error = str(e)
            log_agent_activity(
                task_id=task_id,
                agent_name="ResearchAgent",
                action_details=f"Tool execution failed on attempt {attempt}: {last_error}. Retrying...",
            )
            time.sleep(0.1)

    if research_results is None:
        raise RuntimeError(f"ResearchAgent failed after {max_retries} attempts: {last_error}")

    # Serialize and persist research data to Redis shared scratchpad
    workspace_data = {
        "task_id": task_id,
        "query": prompt,
        "findings": research_results,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    redis_client.save_workspace_sync(task_id, workspace_data)

    log_agent_activity(
        task_id=task_id,
        agent_name="ResearchAgent",
        action_details=f"Persisted research findings to Redis workspace key task:{task_id}:workspace",
    )

    # Append to agent audit logs
    agent_logs.append({
        "agent": "ResearchAgent",
        "action": f"Searching for {prompt[:60]}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "research_data": research_results,
        "agent_logs": agent_logs,
    }
