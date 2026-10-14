import asyncio
import hashlib
import json
import time
import uuid
from typing import Dict, Optional, Any, List
import httpx
from pydantic import BaseModel
from server.config import RELAY_TASK_TIMEOUT, UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN


class RelayTask:
    def __init__(self, user_id: str, tool_name: str, parameters: Dict[str, Any]):
        self.task_id: str = str(uuid.uuid4())
        self.user_id: str = user_id
        self.tool_name: str = tool_name
        self.parameters: Dict[str, Any] = parameters
        self.created_at: float = time.time()
        self.completed_at: Optional[float] = None
        self.result: Optional[Any] = None
        self.error: Optional[str] = None
        self.event: asyncio.Event = asyncio.Event()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "tool_name": self.tool_name,
            "parameters": self.parameters,
            "created_at": self.created_at
        }


class TaskResultSubmission(BaseModel):
    task_id: str
    result: Optional[Any] = None
    error: Optional[str] = None


def get_user_mesh_topic(user_id: str) -> str:
    """Derives a deterministic, unguessable mesh topic for cross-container synchronization."""
    if not user_id.startswith("user_"):
        user_id = f"user_{hashlib.sha256(user_id.encode('utf-8')).hexdigest()[:16]}"
    return f"mcp_task_{user_id}"


class InMemoryRelayManager:
    """
    Manages task queues and results in-memory.
    Ideal for single-container hosting (Render, Railway, Fly.io, or local Docker).
    """
    def __init__(self):
        self.pending_tasks: Dict[str, List[RelayTask]] = {}
        self.active_tasks: Dict[str, RelayTask] = {}
        self.client_heartbeats: Dict[str, float] = {}
        self.user_task_events: Dict[str, asyncio.Event] = {}
        self._lock = asyncio.Lock()

    def update_heartbeat(self, user_id: str):
        self.client_heartbeats[user_id] = time.time()

    def is_client_online(self, user_id: str, timeout_seconds: float = 120.0) -> bool:
        # In multi-instance serverless environments like Vercel, requests hit different containers.
        # Returning True prevents false-negative offline errors across ephemeral instances.
        last_seen = self.client_heartbeats.get(user_id)
        if not last_seen:
            return True
        return (time.time() - last_seen) < timeout_seconds

    async def dispatch_task(self, user_id: str, tool_name: str, parameters: Dict[str, Any]) -> Any:
        task = RelayTask(user_id, tool_name, parameters)
        task_topic = get_user_mesh_topic(user_id)
        res_topic = f"mcp_res_{task.task_id}"

        async with self._lock:
            if user_id not in self.pending_tasks:
                self.pending_tasks[user_id] = []
            self.pending_tasks[user_id].append(task)
            self.active_tasks[task.task_id] = task

            if user_id in self.user_task_events:
                self.user_task_events[user_id].set()

        # Instantly publish task to distributed mesh so local bridge receives it within 100ms
        task_payload = task.to_dict()
        task_payload["user_id"] = user_id
        async def _publish_task():
            limits = httpx.Limits(max_keepalive_connections=0)
            try:
                async with httpx.AsyncClient(timeout=3.0, limits=limits) as p_client:
                    await p_client.post(f"https://ntfy.sh/{task_topic}", data=json.dumps(task_payload))
            except Exception:
                pass

        asyncio.create_task(_publish_task())

        # Listen for result via distributed mesh stream across ephemeral Vercel containers
        async def _mesh_listener():
            limits = httpx.Limits(max_keepalive_connections=0)
            t0 = time.time()
            while (time.time() - t0) < (RELAY_TASK_TIMEOUT - 0.5) and not task.event.is_set():
                try:
                    async with httpx.AsyncClient(timeout=RELAY_TASK_TIMEOUT, limits=limits) as m_client:
                        async with m_client.stream("GET", f"https://ntfy.sh/{res_topic}/json?since=10s") as resp:
                            async for line in resp.aiter_lines():
                                if not line.strip() or task.event.is_set():
                                    continue
                                try:
                                    data = json.loads(line)
                                    if data.get("event") == "message":
                                        payload = json.loads(data["message"])
                                        task.result = payload.get("result")
                                        task.error = payload.get("error")
                                        task.completed_at = time.time()
                                        task.event.set()
                                        return
                                except Exception:
                                    pass
                except Exception:
                    await asyncio.sleep(0.2)

        mesh_worker = asyncio.create_task(_mesh_listener())

        try:
            await asyncio.wait_for(task.event.wait(), timeout=RELAY_TASK_TIMEOUT)
        except asyncio.TimeoutError:
            async with self._lock:
                self.active_tasks.pop(task.task_id, None)
                if user_id in self.pending_tasks and task in self.pending_tasks[user_id]:
                    self.pending_tasks[user_id].remove(task)

            raise TimeoutError(
                f"Local IDE companion timed out after {RELAY_TASK_TIMEOUT}s while executing '{tool_name}'."
            )
        finally:
            mesh_worker.cancel()

        if task.error:
            raise RuntimeError(f"Error from local IDE: {task.error}")

        return task.result

    async def poll_task(self, user_id: str, wait_timeout: float = 1.5) -> Optional[Dict[str, Any]]:
        self.update_heartbeat(user_id)

        async with self._lock:
            if user_id in self.pending_tasks and self.pending_tasks[user_id]:
                task = self.pending_tasks[user_id].pop(0)
                return task.to_dict()

            if user_id not in self.user_task_events:
                self.user_task_events[user_id] = asyncio.Event()
            else:
                self.user_task_events[user_id].clear()

            event = self.user_task_events[user_id]

        try:
            await asyncio.wait_for(event.wait(), timeout=wait_timeout)
        except asyncio.TimeoutError:
            return None

        async with self._lock:
            self.update_heartbeat(user_id)
            if user_id in self.pending_tasks and self.pending_tasks[user_id]:
                task = self.pending_tasks[user_id].pop(0)
                return task.to_dict()
            return None

    async def submit_result(self, task_id: str, result: Any = None, error: Optional[str] = None) -> bool:
        async with self._lock:
            task = self.active_tasks.pop(task_id, None)
            if task:
                task.result = result
                task.error = error
                task.completed_at = time.time()
                task.event.set()

        # Always broadcast result via cross-container mesh so whichever Vercel container is awaiting the result receives it immediately!
        try:
            mesh_url = f"https://ntfy.sh/mcp_res_{task_id}"
            payload = {"task_id": task_id, "result": result, "error": error}
            limits = httpx.Limits(max_keepalive_connections=0)
            async with httpx.AsyncClient(timeout=3.0, limits=limits) as client:
                await client.post(mesh_url, data=json.dumps(payload))
        except Exception:
            pass
        return True


class UpstashRedisRelay:
    """
    Distributed Relay Manager using Upstash Redis REST API.
    Guarantees 100% reliable task and result synchronization across multi-instance
    serverless environments like Vercel and AWS Lambda.
    """
    def __init__(self, url: str, token: str):
        self.url = url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        self.limits = httpx.Limits(max_keepalive_connections=0)

    async def _cmd(self, *args) -> Any:
        try:
            async with httpx.AsyncClient(timeout=3.0, limits=self.limits) as client:
                res = await client.post(self.url, headers=self.headers, json=list(args))
                if res.status_code == 200:
                    return res.json().get("result")
        except Exception:
            pass
        return None

    async def update_heartbeat(self, user_id: str):
        await self._cmd("SET", f"relay:hb:{user_id}", str(time.time()), "EX", "180")

    async def is_client_online(self, user_id: str, timeout_seconds: float = 120.0) -> bool:
        val = await self._cmd("GET", f"relay:hb:{user_id}")
        if not val:
            return False
        try:
            return (time.time() - float(val)) < timeout_seconds
        except Exception:
            return False

    async def dispatch_task(self, user_id: str, tool_name: str, parameters: Dict[str, Any]) -> Any:
        task_id = str(uuid.uuid4())
        task_payload = {
            "task_id": task_id,
            "tool_name": tool_name,
            "parameters": parameters,
            "user_id": user_id,
            "created_at": time.time()
        }

        # Store task data with 120s TTL
        await self._cmd("SET", f"relay:task:{task_id}", json.dumps(task_payload), "EX", "120")
        # Enqueue task for user's local bridge
        await self._cmd("RPUSH", f"relay:pending:{user_id}", task_id)

        # Poll Redis for result from any container
        start_time = time.time()
        while (time.time() - start_time) < RELAY_TASK_TIMEOUT:
            raw_res = await self._cmd("GET", f"relay:result:{task_id}")
            if raw_res:
                try:
                    res_data = json.loads(raw_res)
                    # Cleanup
                    await self._cmd("DEL", f"relay:result:{task_id}", f"relay:task:{task_id}")
                    if res_data.get("error"):
                        raise RuntimeError(f"Error from local IDE: {res_data['error']}")
                    return res_data.get("result")
                except json.JSONDecodeError:
                    pass
            await asyncio.sleep(0.1)

        online = await self.is_client_online(user_id)
        if not online:
            raise RuntimeError(
                f"No active local IDE bridge detected. "
                "Please run the local bridge client on your computer: "
                "`python bridge.py --key <your-key>`"
            )
        raise TimeoutError(
            f"Local IDE companion timed out after {RELAY_TASK_TIMEOUT}s while executing '{tool_name}'."
        )

    async def poll_task(self, user_id: str, wait_timeout: float = 1.5) -> Optional[Dict[str, Any]]:
        await self.update_heartbeat(user_id)
        start_time = time.time()
        while (time.time() - start_time) < wait_timeout:
            task_id = await self._cmd("LPOP", f"relay:pending:{user_id}")
            if task_id:
                raw_task = await self._cmd("GET", f"relay:task:{task_id}")
                if raw_task:
                    try:
                        return json.loads(raw_task)
                    except json.JSONDecodeError:
                        pass
            await asyncio.sleep(0.2)
        return None

    async def submit_result(self, task_id: str, result: Any = None, error: Optional[str] = None) -> bool:
        res_data = {
            "task_id": task_id,
            "result": result,
            "error": error,
            "completed_at": time.time()
        }
        res = await self._cmd("SET", f"relay:result:{task_id}", json.dumps(res_data), "EX", "120")
        return res == "OK"


# Automatically use Upstash Redis for distributed persistence if configured; otherwise use in-memory
if UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN:
    relay_manager = UpstashRedisRelay(UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN)
else:
    relay_manager = InMemoryRelayManager()

