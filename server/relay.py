import asyncio
import time
import uuid
from typing import Dict, Optional, Any, List
from pydantic import BaseModel
from server.config import RELAY_TASK_TIMEOUT


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


class RelayManager:
    """
    Manages task queues and results between Cloud MCP and Local IDE companions.
    Thread-safe and async-compatible.
    """
    def __init__(self):
        # user_id -> List[RelayTask] (pending tasks waiting to be picked up by local IDE)
        self.pending_tasks: Dict[str, List[RelayTask]] = {}
        # task_id -> RelayTask (all active tasks waiting for completion)
        self.active_tasks: Dict[str, RelayTask] = {}
        # user_id -> float (timestamp of last heartbeat / poll from local client)
        self.client_heartbeats: Dict[str, float] = {}
        # user_id -> asyncio.Event (signals when a new task is added for the user)
        self.user_task_events: Dict[str, asyncio.Event] = {}
        self._lock = asyncio.Lock()

    def update_heartbeat(self, user_id: str):
        self.client_heartbeats[user_id] = time.time()

    def is_client_online(self, user_id: str, timeout_seconds: float = 90.0) -> bool:
        last_seen = self.client_heartbeats.get(user_id)
        if not last_seen:
            return False
        return (time.time() - last_seen) < timeout_seconds

    async def dispatch_task(self, user_id: str, tool_name: str, parameters: Dict[str, Any]) -> Any:
        """
        Dispatches a tool call task to the user's local IDE companion and awaits the result.
        """
        if not self.is_client_online(user_id):
            now = time.time()
            active_clients = [uid for uid, t in self.client_heartbeats.items() if (now - t) < 90.0]
            if active_clients:
                user_id = max(active_clients, key=lambda u: self.client_heartbeats.get(u, 0))
            else:
                raise RuntimeError(
                    f"No active local IDE bridge detected. "
                    "Please run the local bridge client on your computer: "
                    "`python bridge.py --key <your-key>`"
                )

        task = RelayTask(user_id, tool_name, parameters)

        async with self._lock:
            if user_id not in self.pending_tasks:
                self.pending_tasks[user_id] = []
            self.pending_tasks[user_id].append(task)
            self.active_tasks[task.task_id] = task

            # Notify any long-polling local client for this user
            if user_id in self.user_task_events:
                self.user_task_events[user_id].set()

        try:
            # Await completion from local client
            await asyncio.wait_for(task.event.wait(), timeout=RELAY_TASK_TIMEOUT)
        except asyncio.TimeoutError:
            async with self._lock:
                self.active_tasks.pop(task.task_id, None)
                if user_id in self.pending_tasks and task in self.pending_tasks[user_id]:
                    self.pending_tasks[user_id].remove(task)
            raise TimeoutError(
                f"Local IDE companion timed out after {RELAY_TASK_TIMEOUT}s while executing '{tool_name}'."
            )

        if task.error:
            raise RuntimeError(f"Error from local IDE: {task.error}")

        return task.result

    async def poll_task(self, user_id: str, wait_timeout: float = 1.5) -> Optional[Dict[str, Any]]:
        """
        Called by local IDE companion to receive work. Supports long-polling.
        """
        self.update_heartbeat(user_id)

        # Check if already a task queued
        async with self._lock:
            if user_id in self.pending_tasks and self.pending_tasks[user_id]:
                task = self.pending_tasks[user_id].pop(0)
                return task.to_dict()

            if user_id not in self.user_task_events:
                self.user_task_events[user_id] = asyncio.Event()
            else:
                self.user_task_events[user_id].clear()

            event = self.user_task_events[user_id]

        # Wait for new task or timeout
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
        """
        Called by local IDE companion to report the execution result.
        """
        async with self._lock:
            task = self.active_tasks.pop(task_id, None)
            if not task:
                return False

            task.result = result
            task.error = error
            task.completed_at = time.time()
            task.event.set()
            return True


# Global singleton instance for the server process
relay_manager = RelayManager()
