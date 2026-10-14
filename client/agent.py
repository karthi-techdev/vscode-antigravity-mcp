import argparse
import asyncio
import os
import sys
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
            "Content-Type": "application/json"
        }
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
        print(f"=======================================================\n")
        print("Connected to cloud relay. Waiting for AI commands (ChatGPT, Gemini, etc.)...\n")

        poll_url = f"{self.server_url}/api/relay/poll"
        result_url = f"{self.server_url}/api/relay/result"

        async with httpx.AsyncClient(timeout=15.0) as client:
            keepalive_task = asyncio.create_task(self._keepalive_loop(client))
            workers = [
                asyncio.create_task(self._poll_worker(i, client, poll_url, result_url))
                for i in range(3)
            ]
            try:
                await asyncio.gather(*workers)
            except asyncio.CancelledError:
                pass
            finally:
                self.running = False
                keepalive_task.cancel()
                for w in workers:
                    w.cancel()

    async def _poll_worker(self, worker_id: int, client: httpx.AsyncClient, poll_url: str, result_url: str):
        """Worker that polls cloud relay for tasks and submits results with retry."""
        consecutive_errors = 0
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
                consecutive_errors = 0
                task = data.get("task")
                if not task:
                    continue

                task_id = task.get("task_id")
                tool_name = task.get("tool_name")
                params = task.get("parameters", {})

                print(f"⚡ [AI REQUEST] Tool: {tool_name} | Params: {params}")
                result, error = None, None
                try:
                    result = await self.execute_task(tool_name, params)
                    print(f"✅ [SUCCESS] Finished {tool_name}")
                except Exception as e:
                    error = str(e)
                    print(f"❌ [TOOL ERROR] {error}")

                # Submit result back to the waiting Vercel instance with retry
                for attempt in range(8):
                    try:
                        res = await client.post(
                            result_url,
                            headers=self.headers,
                            json={"task_id": task_id, "result": result, "error": error},
                            timeout=8.0
                        )
                        if res.status_code == 200:
                            break
                        await asyncio.sleep(0.12)
                    except Exception:
                        await asyncio.sleep(0.15)

            except (httpx.ConnectError, httpx.TimeoutException):
                consecutive_errors += 1
                wait_time = min(5, 2 ** min(consecutive_errors, 2))
                await asyncio.sleep(wait_time)
            except asyncio.CancelledError:
                break
            except Exception as e:
                await asyncio.sleep(0.5)


def handle_startup_installation(server: str, key: str, root_dir: str, uninstall: bool = False):
    """Installs or uninstalls the bridge in Windows Startup."""
    if sys.platform != "win32":
        print("Startup service auto-installer is currently supported on Windows.")
        return

    startup_dir = Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Startup"
    if not startup_dir.exists():
        print(f"❌ Windows Startup directory not found at {startup_dir}")
        return

    vbs_path = startup_dir / "UniversalIDEGlobalBridge.vbs"
    legacy_vbs = startup_dir / "AntigravityGlobalBridge.vbs"

    if uninstall:
        removed = False
        for path in (vbs_path, legacy_vbs):
            if path.exists():
                path.unlink()
                removed = True
        if removed:
            print("✅ Removed Universal IDE Global Bridge from Windows Startup.")
        else:
            print("Notice: Universal IDE Global Bridge was not installed in Startup.")
        return

    if legacy_vbs.exists():
        legacy_vbs.unlink()

    python_exe = sys.executable
    script_path = Path(__file__).resolve()

    vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.Run """{python_exe}"" ""{script_path}"" --server ""{server}"" --key ""{key}"" --root ""{root_dir}""", 0, False
'''
    with open(vbs_path, "w", encoding="utf-8") as f:
        f.write(vbs_content)

    print(f"\n=======================================================")
    print(f"🎉 Universal IDE Global Bridge successfully installed!")
    print(f"📁 Root: {root_dir}")
    print(f"📍 Location: {vbs_path}")
    print(f"⚡ It will now run silently in the background on every Windows boot.")
    print(f"=======================================================\n")


def main():
    parser = argparse.ArgumentParser(description="Universal IDE Global Multi-Project Bridge")
    parser.add_argument("--server", default=os.getenv("MCP_SERVER_URL", "https://vscode-antigravity-mcp.vercel.app"), help="Cloud MCP Server URL")
    parser.add_argument("--key", default=os.getenv("MCP_AUTH_TOKEN", ""), help="User Auth Token")
    parser.add_argument("--dir", default=os.getenv("MCP_WORKSPACE_DIR", "."), help="Path to initial workspace or project")
    parser.add_argument("--root", default=os.getenv("MCP_PROJECTS_ROOT", None), help="Parent directory containing all projects (e.g. C:\\projects)")
    parser.add_argument("--install-startup", action="store_true", help="Install bridge to run silently in the background on Windows startup")
    parser.add_argument("--uninstall-startup", action="store_true", help="Remove bridge from Windows startup")

    args = parser.parse_args()

    if args.install_startup or args.uninstall_startup:
        if not args.key and not args.uninstall_startup:
            print("❌ Error: --key is required to install in Startup.")
            sys.exit(1)
        root = args.root or str(Path(args.dir).resolve().parent if Path(args.dir).name != "projects" else Path(args.dir).resolve())
        handle_startup_installation(args.server, args.key, root, uninstall=args.uninstall_startup)
        return

    if not args.key:
        print("❌ Error: Authentication token is required.")
        print("Specify --key <your-token> or set MCP_AUTH_TOKEN in environment / .env file.")
        sys.exit(1)

    while True:
        try:
            agent = LocalBridgeAgent(
                server_url=args.server,
                auth_token=args.key,
                workspace_dir=args.dir,
                projects_root=args.root
            )
            asyncio.run(agent.run())
        except KeyboardInterrupt:
            print("\n👋 Disconnected by user.")
            break
        except Exception as e:
            print(f"⚠️ Bridge connection interrupted ({e}). Auto-reconnecting in 3 seconds...")
            time.sleep(3)


if __name__ == "__main__":
    main()
