import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

import httpx
from dotenv import load_dotenv

# Ensure project root is in sys.path so client can be run from any workspace directory
_root = Path(__file__).parent.parent.resolve()
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from client.executor import LocalIDEExecutor

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()


def get_user_mesh_topic(token: str) -> str:
    """Derives a deterministic, unguessable mesh topic matching the gateway."""
    if not token.startswith("user_"):
        token = f"user_{hashlib.sha256(token.encode('utf-8')).hexdigest()[:16]}"
    return f"mcp_task_{token}"


class LocalBridgeAgent:
    """
    Connects local IDE / workspace to the cloud MCP server via outbound polling.
    Supports system-wide multi-project switching and zero-inbound ports.
    """
    def __init__(self, server_url: str, auth_token: str, workspace_dir: str = ".", projects_root: Optional[str] = None):
        self.server_url = server_url.rstrip("/")
        self.auth_token = auth_token
        self.executor = LocalIDEExecutor(workspace_dir=workspace_dir, projects_root=projects_root)
        self.headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "User-Agent": "Universal-IDE-Bridge/1.0",
            "Content-Type": "application/json",
            "Connection": "close"
        }
        self.mesh_task_topic = get_user_mesh_topic(self.auth_token)
        self.seen_task_ids = set()
        self.task_lock = asyncio.Lock()
        self.running = False

    def _execute_sync(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        """Route incoming tool request to the appropriate executor method synchronously."""
        p = parameters or {}

        def _get(*keys, default=None):
            for k in keys:
                if k in p and p[k] is not None:
                    return p[k]
            return default

        # System-Wide Multi-Project Management
        if tool_name in ("list_projects", "get_projects"):
            return self.executor.list_projects()
        elif tool_name in ("set_active_project", "switch_project"):
            return self.executor.set_active_project(_get("project_name", "project", "name", default=""))
        elif tool_name in ("get_active_project", "current_project"):
            return self.executor.get_active_project()

        # Workspace Code & File Operations
        elif tool_name in ("read_workspace_file", "read_file"):
            return self.executor.read_file(
                path=_get("path", "file_path", "filepath", "target", "file", default=""),
                max_lines=int(_get("max_lines", "limit", default=500)),
                start_line=int(_get("start_line", "offset", default=1)),
                project=_get("project")
            )
        elif tool_name in ("write_workspace_file", "write_file"):
            return self.executor.write_file(
                path=_get("path", "file_path", "filepath", "target", "file", default=""),
                content=_get("content", "text", "file_content", "body", "data", default=""),
                project=_get("project")
            )
        elif tool_name in ("edit_workspace_file", "edit_file"):
            return self.executor.edit_file(
                path=_get("path", "file_path", "filepath", "target", "file", default=""),
                old_str=_get("old_str", "old_text", "search", "target", "old_content", default=""),
                new_str=_get("new_str", "new_text", "replacement", "replace", "new_content", default=""),
                project=_get("project")
            )
        elif tool_name in ("create_directory", "create_workspace_directory", "mkdir"):
            return self.executor.create_directory(
                path=_get("path", "directory", "dir_path", "dir", default=""),
                project=_get("project")
            )
        elif tool_name in ("delete_file", "delete_workspace_file", "remove_file", "rm"):
            return self.executor.delete_file(
                path=_get("path", "file_path", "filepath", "target", default=""),
                recursive=bool(_get("recursive", "force", default=False)),
                project=_get("project")
            )
        elif tool_name in ("move_or_rename_file", "move_file", "rename_file", "move_workspace_file"):
            return self.executor.move_or_rename_file(
                source_path=_get("source_path", "source", "src", "old_path", default=""),
                destination_path=_get("destination_path", "destination", "dest", "new_path", default=""),
                overwrite=bool(_get("overwrite", default=False)),
                project=_get("project")
            )
        elif tool_name in ("get_file_info", "file_info", "get_workspace_file_info"):
            return self.executor.get_file_info(
                path=_get("path", "file_path", "filepath", "target", default=""),
                project=_get("project")
            )
        elif tool_name in ("list_workspace_directory", "list_directory", "ls"):
            return self.executor.list_directory(
                path=_get("path", "directory", "dir_path", default="."),
                max_depth=int(_get("max_depth", "depth", default=2)),
                project=_get("project")
            )
        elif tool_name in ("search_workspace_files", "search_files", "grep"):
            return self.executor.search_files(
                query=_get("query", "search_query", "pattern", "text", "term", default=""),
                path=_get("path", "directory", default="."),
                file_pattern=_get("file_pattern", "pattern", "filter", default="*"),
                project=_get("project")
            )
        elif tool_name in ("run_terminal_command", "execute_command"):
            return self.executor.execute_command(
                command=_get("command", "cmd", "script", default=""),
                timeout_seconds=int(_get("timeout_seconds", "timeout", default=30)),
                project=_get("project")
            )
        elif tool_name in ("run_powershell_command", "run_powershell", "powershell"):
            return self.executor.run_powershell(
                command=_get("command", "cmd", "script", default=""),
                timeout_seconds=int(_get("timeout_seconds", "timeout", default=60)),
                project=_get("project")
            )
        elif tool_name in ("run_cmd_command", "run_cmd", "cmd"):
            return self.executor.run_cmd(
                command=_get("command", "cmd", "script", default=""),
                timeout_seconds=int(_get("timeout_seconds", "timeout", default=60)),
                project=_get("project")
            )
        elif tool_name in ("run_git_command", "run_git", "git_command", "git"):
            return self.executor.run_git(
                subcommand=_get("subcommand", "command", "cmd", "git_cmd", default=""),
                timeout_seconds=int(_get("timeout_seconds", "timeout", default=60)),
                project=_get("project")
            )
        elif tool_name in ("get_workspace_context", "get_context"):
            return self.executor.get_context()
        else:
            raise NotImplementedError(f"Tool '{tool_name}' is not recognized by the local bridge.")

    async def execute_task(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        """Runs tool in an asynchronous worker thread to prevent blocking event loop."""
        return await asyncio.to_thread(self._execute_sync, tool_name, parameters)

    async def _keepalive_loop(self, client: httpx.AsyncClient):
        """Pings both /health and /api/relay/heartbeat every 20 seconds to keep serverless containers active and warm."""
        health_url = f"{self.server_url}/health"
        heartbeat_url = f"{self.server_url}/api/relay/heartbeat"
        while self.running:
            try:
                await asyncio.sleep(20)
                if not self.running:
                    break
                await client.get(health_url, timeout=5.0)
                await client.post(heartbeat_url, headers=self.headers, timeout=5.0)
            except Exception:
                pass

    async def handle_task(self, task: Dict[str, Any], source: str = "Mesh"):
        """Executes a received task and delivers the result back via mesh and HTTP."""
        task_id = task.get("task_id")
        if not task_id:
            return

        async with self.task_lock:
            if task_id in self.seen_task_ids:
                return
            self.seen_task_ids.add(task_id)

        tool_name = task.get("tool_name")
        params = task.get("parameters", {})

        now_str = datetime.now().strftime("%H:%M:%S")
        print("\n" + "─" * 70, flush=True)
        print(f"⚡ [{now_str}] INCOMING AI REQUEST: {tool_name} (via {source})", flush=True)
        print(f"📦 Parameters: {json.dumps(params, ensure_ascii=False)}", flush=True)
        print(f"📁 Target Project: {self.executor.active_project or 'Default Root'} ({self.executor.current_workspace_path})", flush=True)
        print(f"⚙️ Executing local action...", flush=True)

        t0 = time.time()
        result, error = None, None
        try:
            result = await self.execute_task(tool_name, params)
            exec_ms = round((time.time() - t0) * 1000, 1)
            print(f"✅ Local execution completed successfully in {exec_ms}ms", flush=True)
            preview = str(result)
            if len(preview) > 220:
                preview = preview[:220] + "... [truncated]"
            print(f"📊 Result: {preview}", flush=True)
        except Exception as e:
            error = str(e)
            exec_ms = round((time.time() - t0) * 1000, 1)
            print(f"❌ Local execution failed after {exec_ms}ms: {error}", flush=True)

        # Deliver result concurrently to both distributed mesh and HTTP gateway to prevent network hangs
        async def _deliver_mesh():
            try:
                mesh_url = f"https://ntfy.sh/mcp_res_{task_id}"
                limits = httpx.Limits(max_keepalive_connections=0)
                async with httpx.AsyncClient(timeout=3.0, limits=limits) as m_client:
                    await m_client.post(mesh_url, data=json.dumps({"task_id": task_id, "result": result, "error": error}))
            except Exception:
                pass

        async def _deliver_http():
            try:
                limits = httpx.Limits(max_keepalive_connections=0)
                async with httpx.AsyncClient(timeout=6.0, limits=limits) as res_client:
                    await res_client.post(
                        f"{self.server_url}/api/relay/result",
                        headers=self.headers,
                        json={"task_id": task_id, "result": result, "error": error}
                    )
            except Exception:
                pass

        await asyncio.gather(_deliver_mesh(), _deliver_http(), return_exceptions=True)
        deliv_ms = round((time.time() - t0) * 1000, 1)
        print(f"🚀 Delivered result to AI assistant in {deliv_ms}ms", flush=True)

        print("─" * 70 + "\n", flush=True)

    async def _mesh_stream_worker(self):
        """Persistent SSE/JSON stream worker for sub-100ms task reception."""
        url = f"https://ntfy.sh/{self.mesh_task_topic}/json?since=20s"
        limits = httpx.Limits(max_keepalive_connections=0)
        while self.running:
            try:
                async with httpx.AsyncClient(timeout=None, limits=limits) as client:
                    async with client.stream("GET", url) as resp:
                        async for line in resp.aiter_lines():
                            if not self.running:
                                break
                            if not line.strip():
                                continue
                            try:
                                msg = json.loads(line)
                                if msg.get("event") == "message":
                                    task = json.loads(msg["message"])
                                    asyncio.create_task(self.handle_task(task, source="Zero-Latency Mesh"))
                            except Exception:
                                pass
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(1.0)

    async def _mesh_poll_worker(self):
        """High-frequency mesh polling fallback (checks every 0.8s) guaranteeing zero dropped tasks."""
        url = f"https://ntfy.sh/{self.mesh_task_topic}/json?poll=1&since=25s"
        limits = httpx.Limits(max_keepalive_connections=0)
        while self.running:
            try:
                async with httpx.AsyncClient(timeout=2.0, limits=limits) as client:
                    resp = await client.get(url)
                    if resp.status_code == 200 and resp.text.strip():
                        for line in resp.text.strip().splitlines():
                            try:
                                msg = json.loads(line)
                                if msg.get("event") == "message":
                                    task = json.loads(msg["message"])
                                    asyncio.create_task(self.handle_task(task, source="High-Frequency Mesh"))
                            except Exception:
                                pass
            except asyncio.CancelledError:
                break
            except Exception:
                pass
            await asyncio.sleep(0.8)

    async def _poll_worker(self, worker_id: int, client: httpx.AsyncClient, poll_url: str):
        """Worker that polls cloud relay for tasks as backup."""
        while self.running:
            try:
                response = await client.post(poll_url, headers=self.headers, json={"wait_timeout": 1.5})
                if response.status_code == 401:
                    print(f"❌ Authentication failed: Invalid token '{self.auth_token}'. Exiting.")
                    self.running = False
                    break
                if response.status_code != 200:
                    await asyncio.sleep(0.5)
                    continue

                data = response.json()
                task = data.get("task")
                if task:
                    await self.handle_task(task, source="HTTP Gateway")
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(0.5)

    async def run(self):
        """Main event loop: poll for jobs, execute, and return results."""
        self.running = True
        print(f"\n=======================================================")
        print(f"🚀 Universal IDE Global Bridge Started")
        print(f"📁 Projects Root:  {self.executor.projects_root}")
        if self.executor.active_project:
            print(f"🎯 Active Project: {self.executor.active_project}")
        print(f"🌐 Cloud Relay:    {self.server_url}")
        print(f"🔑 Auth Token:     {self.auth_token[:8]}...{self.auth_token[-4:] if len(self.auth_token) > 12 else ''}")
        if sys.platform == "win32":
            print(f"🛡️ Defender Tip:   If AI tools experience timeouts, run: 'python -m client.agent --allow-defender'")
        print(f"=======================================================\n")
        print("Connected to cloud relay. Waiting for AI commands (ChatGPT, Claude, etc.)...\n")

        poll_url = f"{self.server_url}/api/relay/poll"

        limits = httpx.Limits(max_keepalive_connections=0, max_connections=20)
        async with httpx.AsyncClient(timeout=15.0, limits=limits) as client:
            keepalive_task = asyncio.create_task(self._keepalive_loop(client))
            mesh_stream_task = asyncio.create_task(self._mesh_stream_worker())
            mesh_poll_task = asyncio.create_task(self._mesh_poll_worker())
            poll_tasks = [
                asyncio.create_task(self._poll_worker(i, client, poll_url))
                for i in range(2)
            ]
            all_tasks = [keepalive_task, mesh_stream_task, mesh_poll_task] + poll_tasks
            try:
                await asyncio.gather(mesh_stream_task, mesh_poll_task, *poll_tasks, return_exceptions=True)
            except asyncio.CancelledError:
                pass
            finally:
                self.running = False
                for t in all_tasks:
                    t.cancel()
                await asyncio.sleep(0.5)


CONFIG_FILE = Path.home() / ".universal_ide_bridge.json"


def configure_defender_exclusions(projects_root: Optional[str] = None):
    """
    Adds Windows Defender exclusions for the Python interpreter and project directories
    to prevent Defender from intercepting or delaying AI command execution.
    Requires elevated Administrator privileges (triggers Windows UAC prompt).
    """
    if sys.platform != "win32":
        print("ℹ️ Windows Defender exclusions are only applicable on Windows.")
        return

    python_exe = sys.executable
    python_dir = str(Path(python_exe).parent.resolve())
    root_path = str(Path(projects_root or ".").resolve())
    script_dir = str(Path(__file__).parent.parent.resolve())

    target_paths = list(dict.fromkeys([root_path, script_dir, python_dir]))
    target_procs = list(dict.fromkeys([Path(python_exe).name, "python.exe"]))

    print("\n" + "=" * 70)
    print("🛡️ Configuring Windows Security Defender Exclusions")
    print("=" * 70)
    print("Target Exclusions:")
    for p in target_paths:
        print(f"   📁 Folder:  {p}")
    for proc in target_procs:
        print(f"   ⚙️ Process: {proc}")
    print("\nRequesting Windows Administrator approval (UAC prompt)...")

    # Generate a temporary .ps1 script file to prevent command-line quoting and space issues
    ps_lines = [
        "# Temporary Windows Defender configuration script",
        "$ErrorActionPreference = 'SilentlyContinue'"
    ]
    for p in target_paths:
        escaped_p = p.replace("'", "''")
        ps_lines.append(f"Add-MpPreference -ExclusionPath '{escaped_p}'")
    for proc in target_procs:
        escaped_proc = proc.replace("'", "''")
        ps_lines.append(f"Add-MpPreference -ExclusionProcess '{escaped_proc}'")

    ps_lines.append('Write-Host ""')
    ps_lines.append('Write-Host "[SUCCESS] Windows Defender exclusions configured successfully!" -ForegroundColor Green')
    ps_lines.append('Write-Host "Workspaces and Python are now whitelisted from false positives and timeouts." -ForegroundColor Cyan')
    ps_lines.append('Start-Sleep -Seconds 3')

    temp_script = tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8")
    try:
        temp_script.write("\r\n".join(ps_lines))
        temp_script.close()

        # Execute the script via elevated Start-Process using clean argument array
        # This completely avoids all string escaping and whitespace issues on Windows
        script_file = temp_script.name.replace("'", "''")
        uac_launcher = (
            f"$script = '{script_file}'; "
            f"Start-Process powershell.exe -Verb RunAs -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $script) -Wait"
        )

        subprocess.run(["powershell.exe", "-NoProfile", "-Command", uac_launcher], check=True)
        print("✅ UAC authorization prompt dispatched.")
        print("👉 Please click 'Yes' in the Windows prompt to apply the exclusions immediately.\n")
    except Exception as e:
        print(f"❌ Could not automatically request UAC: {e}")
        print("\nManual Alternative (Open PowerShell as Administrator and run):")
        for p in target_paths:
            print(f"   Add-MpPreference -ExclusionPath '{p}'")
        for proc in target_procs:
            print(f"   Add-MpPreference -ExclusionProcess '{proc}'")
        print()
    finally:
        try:
            if os.path.exists(temp_script.name):
                os.unlink(temp_script.name)
        except Exception:
            pass


def load_saved_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def main():
    parser = argparse.ArgumentParser(description="Universal IDE Global Multi-Project Bridge (On-Demand Session)")
    saved = load_saved_config()

    default_server = saved.get("server") or os.getenv("MCP_SERVER_URL", "https://vscode-antigravity-mcp.vercel.app")
    default_key = saved.get("key") or os.getenv("MCP_AUTH_TOKEN", "D4_PROJECT_MCP_SERVER")
    default_root = saved.get("root") or os.getenv("MCP_PROJECTS_ROOT", "C:\\projects" if Path("C:\\projects").exists() else ".")

    parser.add_argument("--server", "-s", default=default_server, help=f"Cloud MCP Server URL (default: {default_server})")
    parser.add_argument("--key", "-k", "--token", dest="key", default=default_key, help="User Auth Token")
    parser.add_argument("--dir", default=os.getenv("MCP_WORKSPACE_DIR", "."), help="Path to initial workspace or project")
    parser.add_argument("--root", "-r", default=default_root, help=f"Parent directory containing all projects (default: {default_root})")
    parser.add_argument("--allow-defender", action="store_true", help="Add Windows Defender exclusions for your workspace and Python (requires Admin UAC)")

    args = parser.parse_args()

    if getattr(args, "allow_defender", False):
        configure_defender_exclusions(args.root)
        return

    agent = LocalBridgeAgent(
        server_url=args.server,
        auth_token=args.key,
        workspace_dir=args.dir,
        projects_root=args.root
    )

    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        print("\n" + "─" * 70)
        print("🛑 Bridge session stopped by user (Ctrl+C). Clean shutdown complete.")
        print("👋 Goodbye!\n")
    except Exception as e:
        print(f"\n❌ Bridge stopped with error: {e}")


if __name__ == "__main__":
    main()
