import json
import redis
import redis.asyncio as aioredis
from typing import Any, AsyncGenerator, Dict, Optional, Union

from src.config.settings import settings


class RedisClient:
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or settings.REDIS_URL
        self._sync_client: Optional[redis.Redis] = None
        self._async_client: Optional[aioredis.Redis] = None

    @property
    def sync_client(self) -> redis.Redis:
        if self._sync_client is None:
            self._sync_client = redis.from_url(self.redis_url, decode_responses=True)
        return self._sync_client

    @property
    def async_client(self) -> aioredis.Redis:
        if self._async_client is None:
            self._async_client = aioredis.from_url(self.redis_url, decode_responses=True)
        return self._async_client

    # --- Ephemeral Scratchpad Workspace ---
    def get_workspace_key(self, task_id: str) -> str:
        return f"task:{task_id}:workspace"

    def get_channel_name(self, task_id: str) -> str:
        return f"task_updates:{task_id}"

    def save_workspace_sync(self, task_id: str, data: Union[Dict[str, Any], str], ttl: int = 86400) -> None:
        """Save intermediate agent data to Redis workspace key synchronously."""
        key = self.get_workspace_key(task_id)
        value = json.dumps(data) if isinstance(data, (dict, list)) else str(data)
        self.sync_client.set(key, value, ex=ttl)

    def get_workspace_sync(self, task_id: str) -> Optional[Any]:
        """Retrieve intermediate agent data from Redis workspace key synchronously."""
        key = self.get_workspace_key(task_id)
        val = self.sync_client.get(key)
        if val is None:
            return None
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return val

    async def save_workspace_async(self, task_id: str, data: Union[Dict[str, Any], str], ttl: int = 86400) -> None:
        """Save intermediate agent data to Redis workspace key asynchronously."""
        key = self.get_workspace_key(task_id)
        value = json.dumps(data) if isinstance(data, (dict, list)) else str(data)
        await self.async_client.set(key, value, ex=ttl)

    async def get_workspace_async(self, task_id: str) -> Optional[Any]:
        """Retrieve intermediate agent data from Redis workspace key asynchronously."""
        key = self.get_workspace_key(task_id)
        val = await self.async_client.get(key)
        if val is None:
            return None
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return val

    # --- Real-time Pub/Sub Status Updates ---
    def publish_status_sync(self, task_id: str, status: str) -> None:
        """Publish status change event via Redis Pub/Sub synchronously."""
        channel = self.get_channel_name(task_id)
        payload = json.dumps({"task_id": str(task_id), "status": status})
        self.sync_client.publish(channel, payload)

    async def publish_status_async(self, task_id: str, status: str) -> None:
        """Publish status change event via Redis Pub/Sub asynchronously."""
        channel = self.get_channel_name(task_id)
        payload = json.dumps({"task_id": str(task_id), "status": status})
        await self.async_client.publish(channel, payload)

    async def subscribe_status_async(self, task_id: str) -> AsyncGenerator[str, None]:
        """Async generator that subscribes to task status updates."""
        channel = self.get_channel_name(task_id)
        pubsub = self.async_client.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield message["data"]
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()


redis_client = RedisClient()
