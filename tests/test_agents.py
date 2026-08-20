import pytest
import os
import json
from unittest.mock import patch, MagicMock

from src.agents.tools import simulated_search_tool, reset_flaky_attempts
from src.agents.research_agent import research_agent_node
from src.agents.writing_agent import writing_agent_node
from src.agents.workflow import run_phase1_workflow, run_phase2_workflow
from src.redis_client.client import redis_client


def test_simulated_search_tool_normal():
    """Test standard technical search query."""
    res = simulated_search_tool("Research LangGraph and CrewAI features")
    assert "LangGraph" in res
    assert "CrewAI" in res


def test_simulated_search_tool_flaky_retry():
    """Test flaky query fails first attempt and succeeds on second attempt."""
    reset_flaky_attempts()
    query = "__FLAKY_TEST__"

    # Attempt 1: Must raise simulated network exception
    with pytest.raises(Exception) as exc_info:
        simulated_search_tool(query)
    assert "Simulated transient network timeout." in str(exc_info.value)

    # Attempt 2: Must succeed
    res = simulated_search_tool(query)
    assert "Search results retrieved on second attempt" in res


def test_research_agent_node_with_flaky_retry(mock_redis):
    """Test ResearchAgent node handles flaky tool failure, retries and succeeds."""
    reset_flaky_attempts()
    task_id = "test-flaky-task-123"
    state = {
        "task_id": task_id,
        "prompt": "Investigate __FLAKY_TEST__ scenario",
        "research_data": None,
        "draft_summary": None,
        "approved": False,
        "feedback": None,
        "agent_logs": [],
        "status": "RUNNING",
        "error": None,
    }

    result = research_agent_node(state)
    assert result["research_data"] is not None
    assert "second attempt" in result["research_data"]
    assert len(result["agent_logs"]) == 1
    assert result["agent_logs"][0]["agent"] == "ResearchAgent"
    assert f"task:{task_id}:workspace" in mock_redis["scratchpad"]


def test_writing_agent_node_with_redis(mock_redis):
    """Test WritingAgent node reads from Redis scratchpad and synthesizes summary."""
    task_id = "test-writing-task-456"
    
    # Pre-populate Redis scratchpad
    redis_client.save_workspace_sync(
        task_id,
        {"findings": "LangGraph has cyclic state graphs; CrewAI has role playing agents."}
    )

    state = {
        "task_id": task_id,
        "prompt": "Compare LangGraph and CrewAI",
        "research_data": "LangGraph has cyclic state graphs; CrewAI has role playing agents.",
        "draft_summary": None,
        "approved": False,
        "feedback": None,
        "agent_logs": [{"agent": "ResearchAgent", "action": "Searched info", "timestamp": "2026-08-16T12:00:00Z"}],
        "status": "RUNNING",
        "error": None,
    }

    result = writing_agent_node(state)
    assert result["draft_summary"] is not None
    assert "LangGraph" in result["draft_summary"]
    assert "CrewAI" in result["draft_summary"]
    assert len(result["agent_logs"]) == 2
    assert result["agent_logs"][1]["agent"] == "WritingAgent"


def test_full_langgraph_workflow(mock_redis):
    """Test Phase 1 and Phase 2 LangGraph orchestration end-to-end."""
    reset_flaky_attempts()
    task_id = "test-full-workflow-789"
    prompt = "Research the key features of LangGraph and CrewAI. Write a short comparison summary for a technical audience."

    # Phase 1: Research -> Writing -> Pause for Approval
    phase1_output = run_phase1_workflow(task_id=task_id, prompt=prompt)
    assert phase1_output["draft_summary"] is not None
    assert len(phase1_output["agent_logs"]) >= 2
    assert phase1_output["agent_logs"][0]["agent"] == "ResearchAgent"
    assert phase1_output["agent_logs"][1]["agent"] == "WritingAgent"
    assert f"task:{task_id}:workspace" in mock_redis["scratchpad"]

    # Phase 2: Resume upon approval
    phase2_output = run_phase2_workflow(
        task_id=task_id,
        prompt=prompt,
        draft_summary=phase1_output["draft_summary"],
        feedback="Include more details on state persistence.",
        agent_logs=phase1_output["agent_logs"],
    )
    assert phase2_output["status"] == "COMPLETED"
    assert "Reviewer Feedback Incorporated" in phase2_output["result"]
