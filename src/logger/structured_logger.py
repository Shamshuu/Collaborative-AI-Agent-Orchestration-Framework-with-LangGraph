import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pathlib import Path


class AgentStructuredLogger:
    def __init__(self, log_file_path: str = "logs/agent_activity.log"):
        self.log_file_path = log_file_path
        log_dir = os.path.dirname(self.log_file_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
            
        self.logger = logging.getLogger(f"agent_activity_{self.log_file_path}")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        
        if not self.logger.handlers:
            handler = logging.FileHandler(self.log_file_path, mode="a", encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(message)s"))
            self.logger.addHandler(handler)

    def log(
        self,
        task_id: str,
        agent_name: str,
        action_details: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Write a structured JSON log line to the agent activity log file."""
        now_utc = datetime.now(timezone.utc).isoformat()
        
        log_entry = {
            "timestamp": now_utc,
            "task_id": str(task_id),
            "agent_name": agent_name,
            "action_details": action_details,
        }
        
        if extra:
            log_entry.update(extra)
            
        json_line = json.dumps(log_entry)
        self.logger.info(json_line)
        for handler in self.logger.handlers:
            handler.flush()
        return log_entry


# Singleton instance
structured_logger = AgentStructuredLogger()


def log_agent_activity(task_id: str, agent_name: str, action_details: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Helper function to log agent activities in structured format."""
    return structured_logger.log(
        task_id=task_id,
        agent_name=agent_name,
        action_details=action_details,
        extra=extra,
    )
