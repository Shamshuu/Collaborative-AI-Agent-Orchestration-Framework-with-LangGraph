import os
import json
import uuid
from src.logger.structured_logger import log_agent_activity, AgentStructuredLogger


def test_structured_logger_json_format(tmp_path):
    """Test that agent structured log lines are independent, valid JSON objects with required keys."""
    log_file = tmp_path / "test_agent_activity.log"
    logger = AgentStructuredLogger(log_file_path=str(log_file))

    task_id = str(uuid.uuid4())
    logger.log(
        task_id=task_id,
        agent_name="ResearchAgent",
        action_details="Starting web search for 'LangGraph features'",
    )
    logger.log(
        task_id=task_id,
        agent_name="WritingAgent",
        action_details="Drafting comparison summary",
    )

    with open(log_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    assert len(lines) == 2
    for line in lines:
        data = json.loads(line)
        assert "timestamp" in data
        assert "task_id" in data
        assert "agent_name" in data
        assert "action_details" in data
        assert data["task_id"] == task_id
