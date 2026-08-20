import pytest
from src.redis_client.client import RedisClient


def test_redis_scratchpad_key_pattern():
    """Test that Redis workspace scratchpad follows task:<task_id>:workspace key pattern."""
    client = RedisClient()
    key = client.get_workspace_key("12345")
    assert key == "task:12345:workspace"

    channel = client.get_channel_name("12345")
    assert channel == "task_updates:12345"
