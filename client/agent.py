import argparse
import asyncio
import os
import sys
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
            "User-Agent": "Antigravity-Local-Bridge/1.0",
            "Content-Type": "application/json"
        }
        self.running = False

    async def execute_task(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        """Route incoming tool request to the appropriate executor method."""
        p = parameters or {}

        # Multi-Project Navigation Tools
        if tool_name in ("list_projects", "get_projects"):
            return self.executor.list_projects()
        elif tool_name in ("set_active_project", "switch_project"):
            return self.executor.set_active_project(p.get("project_name", ""))
        elif tool_name in ("get_active_project", "current_project"):
            return self.executor.get_active_project()

        # Workspace Code & File Operations
        elif tool_name in ("read_workspace_file", "read_file"):
            return self.executor.read_file(
                path=p.get("path", ""),
                max_lines=p.get("max_lines", 500),
                start_line=p.get("start_line", 1),
                project=p.get("project")
            )
        elif tool_name in ("write_workspace_file", "write_file"):
            return self.executor.write_file(
                path=p.get("path", ""),
                content=p.get("content", ""),
                project=p.get("project")
            )
        elif tool_name in ("edit_workspace_file", "edit_file"):
            return self.executor.edit_file(
                path=p.get("path", ""),
                old_str=p.get("old_str", ""),
                new_str=p.get("new_str", ""),
                project=p.get("project")
            )
        elif tool_name in ("create_directory", "create_workspace_directory", "mkdir"):
            return self.executor.create_directory(
                path=p.get("path", ""),
                project=p.get("project")
            )
        elif tool_name in ("delete_file", "delete_workspace_file", "remove_file"):
            return self.executor.delete_file(
                path=p.get("path", ""),
                recursive=p.get("recursive", False),
                project=p.get("project")
            )
        elif tool_name in ("move_or_rename_file", "move_file", "rename_file", "move_workspace_file"):
            return self.executor.move_or_rename_file(
                source_path=p.get("source_path", ""),
                destination_path=p.get("destination_path", ""),
                overwrite=p.get("overwrite", False),
                project=p.get("project")
            )
        elif tool_name in ("get_file_info", "file_info", "get_workspace_file_info"):
            return self.executor.get_file_info(
                path=p.get("path", ""),
                project=p.get("project")
            )
        elif tool_name in ("list_workspace_directory", "list_directory"):
            return self.executor.list_directory(
                path=p.get("path", "."),
                max_depth=p.get("max_depth", 2),
                project=p.get("project")
            )
        elif tool_name in ("search_workspace_files", "search_files"):
            return self.executor.search_files(
                query=p.get("query", ""),
                path=p.get("path", "."),
                file_pattern=p.get("file_pattern", "*"),
                project=p.get("project")
            )
        elif tool_name in ("run_terminal_command", "execute_command"):
            return self.executor.execute_command(
                command=p.get("command", ""),
                timeout_seconds=p.get("timeout_seconds", 30),
                project=p.get("project")
            )
        elif tool_name in ("run_powershell_command", "run_powershell"):
            return self.executor.run_powershell(
                command=p.get("command", ""),
                timeout_seconds=p.get("timeout_seconds", 60),
                project=p.get("project")
            )
        elif tool_name in ("run_cmd_command", "run_cmd"):
            return self.executor.run_cmd(
                command=p.get("command", ""),
                timeout_seconds=p.get("timeout_seconds", 60),
                project=p.get("project")
            )
        elif tool_name in ("run_git_command", "run_git", "git_command"):
            return self.executor.run_git(
                subcommand=p.get("subcommand", p.get("command", "")),
                timeout_seconds=p.get("timeout_seconds", 60),
                project=p.get("project")
            )
        elif tool_name in ("get_workspace_context", "get_context"):
            return self.executor.get_context()
        else:
            raise NotImplementedError(f"Tool '{tool_name}' is not recognized by the local bridge.")

    async def run(self):
        """Main event loop: poll for jobs, execute, and return results."""
        self.running = True
        print(f"\n=======================================================")
        print(f"🚀 Antigravity IDE Global Bridge Started")
        print(f"📁 Projects Root:  {self.executor.projects_root}")
        if self.executor.active_project:
            print(f"🎯 Active Project: {self.executor.active_project}")
        print(f"🌐 Cloud Relay:    {self.server_url}")
        print(f"🔑 Auth Token:     {self.auth_token[:8]}...{self.auth_token[-4:] if len(self.auth_token) > 12 else ''}")
        print(f"=======================================================\n")
        print("Connected to cloud relay. Waiting for AI commands (ChatGPT, Gemini, etc.)...\n")

        poll_url = f"{self.server_url}/api/relay/poll"
        result_url = f"{self.server_url}/api/relay/result"

        async with httpx.AsyncClient(timeout=30.0) as client:
            consecutive_errors = 0

            while self.running:
                try:
                    response = await client.post(poll_url, headers=self.headers, json={"wait_timeout": 15})
                    
                    if response.status_code == 401:
                        print(f"❌ Authentication failed: Invalid token '{self.auth_token}'. Exiting.")
                        self.running = False
                        break

                    if response.status_code != 200:
                        await asyncio.sleep(3)
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

                    result = None
                    error = None
                    try:
                        result = await self.execute_task(tool_name, params)
                        print(f"✅ [SUCCESS] Finished {tool_name}")
                    except Exception as e:
                        error = str(e)
                        print(f"❌ [TOOL ERROR] {error}")

                    await client.post(
                        result_url,
                        headers=self.headers,
                        json={
                            "task_id": task_id,
                            "result": result,
                            "error": error
                        }
                    )

                except (httpx.ConnectError, httpx.TimeoutException):
                    consecutive_errors += 1
                    wait_time = min(10, 2 ** consecutive_errors)
                    print(f"🔄 Connection to cloud relay interrupted. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                except asyncio.CancelledError:
                    print("\n🛑 Local bridge stopping...")
                    self.running = False
                    break
                except Exception as e:
                    print(f"⚠️ Unexpected error: {str(e)}")
                    await asyncio.sleep(2)


def handle_startup_installation(server: str, key: str, root_dir: str, uninstall: bool = False):
    """Installs or uninstalls the bridge in Windows Startup."""
    if sys.platform != "win32":
        print("Startup service auto-installer is currently supported on Windows.")
        return

    startup_dir = Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Startup"
    if not startup_dir.exists():
        print(f"❌ Windows Startup directory not found at {startup_dir}")
        return

    vbs_path = startup_dir / "AntigravityGlobalBridge.vbs"

    if uninstall:
        if vbs_path.exists():
            vbs_path.unlink()
            print("✅ Removed Antigravity Global Bridge from Windows Startup.")
        else:
            print("Notice: Antigravity Global Bridge was not installed in Startup.")
        return

    python_exe = sys.executable
    script_path = Path(__file__).resolve()

    vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.Run """{python_exe}"" ""{script_path}"" --server ""{server}"" --key ""{key}"" --root ""{root_dir}""", 0, False
'''
    with open(vbs_path, "w", encoding="utf-8") as f:
        f.write(vbs_content)

    print(f"\n=======================================================")
    print(f"🎉 Antigravity Global Bridge successfully installed!")
    print(f"📁 Root: {root_dir}")
    print(f"📍 Location: {vbs_path}")
    print(f"⚡ It will now run silently in the background on every Windows boot.")
    print(f"=======================================================\n")


def main():
    parser = argparse.ArgumentParser(description="Antigravity IDE Global Multi-Project Bridge")
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

    agent = LocalBridgeAgent(
        server_url=args.server,
        auth_token=args.key,
        workspace_dir=args.dir,
        projects_root=args.root
    )
    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        print("\n👋 Disconnected.")


if __name__ == "__main__":
    main()
