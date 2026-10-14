"""
Antigravity IDE - Standalone Global Multi-Project Bridge
Connects any project on your computer to Gemini Web / ChatGPT via hosted MCP Gateway (Vercel).
Supports system-wide multi-project switching and background startup.
No git cloning required.
"""

import argparse
import asyncio
import fnmatch
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure httpx is installed
try:
    import httpx
except ImportError:
    print("[!] 'httpx' is required to run the bridge.")
    print("[!] Installing httpx...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx"])
    import httpx


class LocalIDEExecutor:
    """
    Executes actions inside the local user's project workspaces.
    Supports system-wide multi-project discovery, active project switching,
    and directory boundary protection.
    """
    def __init__(self, workspace_dir: str = ".", projects_root: Optional[str] = None):
        target_dir = Path(workspace_dir).resolve()
        
        if projects_root:
            self.projects_root = Path(projects_root).resolve()
        else:
            if target_dir.parent.exists() and target_dir.parent.name in ("projects", "workspace", "repos", "code", "dev"):
                self.projects_root = target_dir.parent
            else:
                self.projects_root = target_dir

        if not self.projects_root.exists():
            self.projects_root.mkdir(parents=True, exist_ok=True)

        if target_dir != self.projects_root and self.projects_root in target_dir.parents:
            self.active_project: Optional[str] = str(target_dir.relative_to(self.projects_root))
        else:
            self.active_project = None

    @property
    def current_workspace_path(self) -> Path:
        if self.active_project:
            return (self.projects_root / self.active_project).resolve()
        return self.projects_root

    def list_projects(self) -> Dict[str, Any]:
        projects: List[Dict[str, Any]] = []
        ignored = {".git", ".venv", "venv", "__pycache__", "node_modules", ".vercel", "$RECYCLE.BIN"}

        if self.projects_root.is_dir():
            for entry in sorted(self.projects_root.iterdir()):
                if entry.is_dir() and entry.name not in ignored:
                    tech = []
                    if (entry / "package.json").exists():
                        tech.append("Node.js")
                    if (entry / "pyproject.toml").exists() or (entry / "requirements.txt").exists():
                        tech.append("Python")
                    if (entry / "Cargo.toml").exists():
                        tech.append("Rust")
                    if (entry / "go.mod").exists():
                        tech.append("Go")
                    if (entry / "pom.xml").exists() or (entry / "build.gradle").exists():
                        tech.append("Java")
                    if (entry / ".git").exists():
                        tech.append("Git")

                    branch = None
                    if (entry / ".git").exists():
                        try:
                            res = subprocess.run(
                                "git rev-parse --abbrev-ref HEAD",
                                cwd=str(entry),
                                shell=True,
                                capture_output=True,
                                text=True,
                                timeout=2
                            )
                            if res.returncode == 0:
                                branch = res.stdout.strip()
                        except Exception:
                            pass

                    projects.append({
                        "name": entry.name,
                        "path": str(entry),
                        "type": ", ".join(tech) if tech else "Directory",
                        "git_branch": branch,
                        "is_active": (self.active_project == entry.name)
                    })

        return {
            "projects_root": str(self.projects_root),
            "active_project": self.active_project,
            "total_projects": len(projects),
            "projects": projects
        }

    def set_active_project(self, project_name: str) -> Dict[str, Any]:
        if not project_name or project_name in (".", "/"):
            self.active_project = None
            return {
                "status": "success",
                "message": f"Cleared active project. Current root is {self.projects_root}",
                "active_project": None,
                "current_path": str(self.projects_root)
            }

        target = (self.projects_root / project_name).resolve()
        if not target.is_dir():
            raise NotADirectoryError(f"Project '{project_name}' not found under '{self.projects_root}'")

        self.active_project = str(target.relative_to(self.projects_root))
        return {
            "status": "success",
            "active_project": self.active_project,
            "current_path": str(target),
            "message": f"Switched active project to '{self.active_project}'"
        }

    def get_active_project(self) -> Dict[str, Any]:
        current = self.current_workspace_path
        git_branch, git_status = None, None
        if (current / ".git").exists():
            try:
                res = subprocess.run(
                    "git rev-parse --abbrev-ref HEAD",
                    cwd=str(current),
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if res.returncode == 0:
                    git_branch = res.stdout.strip()

                st = subprocess.run(
                    "git status --short",
                    cwd=str(current),
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if st.returncode == 0:
                    git_status = st.stdout.strip()
            except Exception:
                pass

        return {
            "projects_root": str(self.projects_root),
            "active_project": self.active_project,
            "active_workspace_path": str(current),
            "git_branch": git_branch,
            "git_status": git_status
        }

    def _resolve_safe_path(self, relative_or_abs_path: str, project: Optional[str] = None) -> Path:
        if project:
            base_dir = (self.projects_root / project).resolve()
            if not base_dir.is_dir():
                raise NotADirectoryError(f"Project '{project}' does not exist.")
        else:
            base_dir = self.current_workspace_path

        target = (base_dir / relative_or_abs_path).resolve()
        try:
            target.relative_to(self.projects_root)
        except ValueError:
            raise PermissionError(
                f"Access denied: '{relative_or_abs_path}' is outside authorized root '{self.projects_root}'"
            )
        return target

    def read_file(self, path: str, max_lines: Optional[int] = 500, start_line: int = 1, project: Optional[str] = None) -> Dict[str, Any]:
        target = self._resolve_safe_path(path, project=project)
        base_dir = (self.projects_root / project).resolve() if project else self.current_workspace_path
        if not target.is_file():
            raise FileNotFoundError(f"File not found: {path}")

        try:
            with open(target, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception as e:
            raise IOError(f"Could not read file {path}: {str(e)}")

        total_lines = len(lines)
        start_idx = max(0, start_line - 1)
        end_idx = start_idx + max_lines if max_lines else total_lines
        selected_lines = lines[start_idx:end_idx]

        content_with_numbers = "".join(
            f"{i + 1:4d} | {line}" for i, line in enumerate(selected_lines, start=start_idx)
        )

        return {
            "path": str(target.relative_to(base_dir)),
            "full_path": str(target),
            "project": project or self.active_project,
            "total_lines": total_lines,
            "start_line": start_line,
            "returned_lines": len(selected_lines),
            "content": content_with_numbers,
            "raw_content": "".join(selected_lines)
        }

    def write_file(self, path: str, content: str, project: Optional[str] = None) -> Dict[str, Any]:
        target = self._resolve_safe_path(path, project=project)
        base_dir = (self.projects_root / project).resolve() if project else self.current_workspace_path
        target.parent.mkdir(parents=True, exist_ok=True)

        with open(target, "w", encoding="utf-8") as f:
            f.write(content)

        return {
            "status": "success",
            "path": str(target.relative_to(base_dir)),
            "full_path": str(target),
            "project": project or self.active_project,
            "bytes_written": len(content.encode("utf-8"))
        }

    def edit_file(self, path: str, old_str: str, new_str: str, project: Optional[str] = None) -> Dict[str, Any]:
        target = self._resolve_safe_path(path, project=project)
        base_dir = (self.projects_root / project).resolve() if project else self.current_workspace_path
        if not target.is_file():
            raise FileNotFoundError(f"File not found: {path}")

        with open(target, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        if old_str not in content:
            raise ValueError(f"Pattern not found in {path}: '{old_str[:100]}...'")

        count = content.count(old_str)
        updated = content.replace(old_str, new_str)

        with open(target, "w", encoding="utf-8") as f:
            f.write(updated)

        return {
            "status": "success",
            "path": str(target.relative_to(base_dir)),
            "full_path": str(target),
            "project": project or self.active_project,
            "replacements_made": count
        }

    def list_directory(self, path: str = ".", max_depth: int = 2, project: Optional[str] = None) -> Dict[str, Any]:
        target = self._resolve_safe_path(path, project=project)
        base_dir = (self.projects_root / project).resolve() if project else self.current_workspace_path
        if not target.is_dir():
            raise NotADirectoryError(f"Directory not found: {path}")

        results: List[Dict[str, Any]] = []
        ignored_dirs = {".git", ".venv", "venv", "__pycache__", "node_modules", ".vercel"}

        for root, dirs, files in os.walk(target):
            dirs[:] = [d for d in dirs if d not in ignored_dirs]
            rel_root = Path(root).relative_to(target)
            depth = len(rel_root.parts)

            if depth > max_depth:
                dirs.clear()
                continue

            for d in sorted(dirs):
                item_path = Path(root) / d
                results.append({"name": d, "path": str(item_path.relative_to(base_dir)), "type": "directory"})

            for f in sorted(files):
                item_path = Path(root) / f
                try:
                    size = item_path.stat().st_size
                except OSError:
                    size = 0
                results.append({"name": f, "path": str(item_path.relative_to(base_dir)), "type": "file", "size_bytes": size})

        return {
            "workspace_root": str(base_dir),
            "project": project or self.active_project,
            "directory": str(target.relative_to(base_dir)) if target != base_dir else ".",
            "entries_count": len(results),
            "entries": results
        }

    def search_files(self, query: str, path: str = ".", file_pattern: str = "*", project: Optional[str] = None) -> Dict[str, Any]:
        target = self._resolve_safe_path(path, project=project)
        matches: List[Dict[str, Any]] = []
        ignored_dirs = {".git", ".venv", "venv", "__pycache__", "node_modules", ".vercel"}

        for root, dirs, files in os.walk(target):
            dirs[:] = [d for d in dirs if d not in ignored_dirs]
            for file_name in files:
                if not fnmatch.fnmatch(file_name, file_pattern):
                    continue

                file_path = Path(root) / file_name
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line_no, line in enumerate(f, 1):
                            if query.lower() in line.lower():
                                matches.append({
                                    "file": str(file_path.relative_to(self.current_workspace_path)),
                                    "line": line_no,
                                    "content": line.strip()
                                })
                                if len(matches) >= 100:
                                    break
                except Exception:
                    continue
                if len(matches) >= 100:
                    break
            if len(matches) >= 100:
                break

        return {"query": query, "workspace": str(self.current_workspace_path), "matches_found": len(matches), "matches": matches}

    def execute_command(self, command: str, timeout_seconds: int = 30, project: Optional[str] = None) -> Dict[str, Any]:
        cwd = self._resolve_safe_path(".", project=project)
        try:
            res = subprocess.run(
                command,
                cwd=str(cwd),
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_seconds
            )
            return {"command": command, "cwd": str(cwd), "exit_code": res.returncode, "stdout": res.stdout, "stderr": res.stderr}
        except subprocess.TimeoutExpired:
            return {"command": command, "cwd": str(cwd), "exit_code": -1, "stdout": "", "stderr": f"Command timed out after {timeout_seconds}s"}
        except Exception as e:
            return {"command": command, "cwd": str(cwd), "exit_code": -1, "stdout": "", "stderr": f"Execution failed: {str(e)}"}

    def get_context(self) -> Dict[str, Any]:
        return self.get_active_project()


class LocalBridgeAgent:
    def __init__(self, server_url: str, auth_token: str, workspace_dir: str = ".", projects_root: Optional[str] = None):
        self.server_url = server_url.rstrip("/")
        self.auth_token = auth_token
        self.executor = LocalIDEExecutor(workspace_dir=workspace_dir, projects_root=projects_root)
        self.headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "User-Agent": "Antigravity-Bridge/1.0",
            "Content-Type": "application/json"
        }
        self.running = False

    async def execute_task(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        p = parameters or {}
        if tool_name in ("list_projects", "get_projects"):
            return self.executor.list_projects()
        elif tool_name in ("set_active_project", "switch_project"):
            return self.executor.set_active_project(p.get("project_name", ""))
        elif tool_name in ("get_active_project", "current_project"):
            return self.executor.get_active_project()
        elif tool_name in ("read_workspace_file", "read_file"):
            return self.executor.read_file(p.get("path", ""), p.get("max_lines", 500), p.get("start_line", 1), project=p.get("project"))
        elif tool_name in ("write_workspace_file", "write_file"):
            return self.executor.write_file(p.get("path", ""), p.get("content", ""), project=p.get("project"))
        elif tool_name in ("edit_workspace_file", "edit_file"):
            return self.executor.edit_file(p.get("path", ""), p.get("old_str", ""), p.get("new_str", ""), project=p.get("project"))
        elif tool_name in ("list_workspace_directory", "list_directory"):
            return self.executor.list_directory(p.get("path", "."), p.get("max_depth", 2), project=p.get("project"))
        elif tool_name in ("search_workspace_files", "search_files"):
            return self.executor.search_files(p.get("query", ""), p.get("path", "."), p.get("file_pattern", "*"), project=p.get("project"))
        elif tool_name in ("run_terminal_command", "execute_command"):
            return self.executor.execute_command(p.get("command", ""), p.get("timeout_seconds", 30), project=p.get("project"))
        elif tool_name in ("get_workspace_context", "get_context"):
            return self.executor.get_context()
        else:
            raise NotImplementedError(f"Tool '{tool_name}' is not recognized.")

    async def run(self):
        self.running = True
        print("=" * 60)
        print("🚀 Antigravity IDE Global Multi-Project Bridge Connected")
        print(f"📁 Projects Root:  {self.executor.projects_root}")
        if self.executor.active_project:
            print(f"🎯 Active Project: {self.executor.active_project}")
        print(f"🌐 Cloud Relay:    {self.server_url}")
        print("=" * 60)
        print("Waiting for AI commands from Gemini / ChatGPT in browser...\n")

        poll_url = f"{self.server_url}/api/relay/poll"
        result_url = f"{self.server_url}/api/relay/result"

        async with httpx.AsyncClient(timeout=30.0) as client:
            consecutive_errors = 0
            while self.running:
                try:
                    response = await client.post(poll_url, headers=self.headers, json={"wait_timeout": 15})
                    if response.status_code == 401:
                        print(f"❌ Auth error: Token rejected by server. Exiting.")
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

                    print(f"⚡ [AI REQUEST] {tool_name} -> {params}")
                    result, error = None, None
                    try:
                        result = await self.execute_task(tool_name, params)
                        print(f"✅ [SUCCESS] {tool_name}")
                    except Exception as e:
                        error = str(e)
                        print(f"❌ [TOOL ERROR] {error}")

                    await client.post(
                        result_url,
                        headers=self.headers,
                        json={"task_id": task_id, "result": result, "error": error}
                    )
                except (httpx.ConnectError, httpx.TimeoutException):
                    consecutive_errors += 1
                    wait_time = min(10, 2 ** consecutive_errors)
                    print(f"🔄 Reconnecting to cloud relay in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                except asyncio.CancelledError:
                    print("\n🛑 Bridge stopped.")
                    self.running = False
                    break
                except Exception as e:
                    print(f"⚠️ Error: {str(e)}")
                    await asyncio.sleep(2)


def handle_startup_installation(server: str, key: str, root_dir: str, uninstall: bool = False):
    if sys.platform != "win32":
        print("Startup service installer is currently supported on Windows.")
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
    print(f"📁 Projects Root: {root_dir}")
    print(f"📍 Location:      {vbs_path}")
    print(f"⚡ It will now run silently in the background on every Windows boot.")
    print(f"=======================================================\n")


def main():
    parser = argparse.ArgumentParser(description="Antigravity IDE Standalone Global Multi-Project Bridge")
    parser.add_argument("--server", default="https://vscode-antigravity-mcp.vercel.app", help="Cloud MCP Server URL")
    parser.add_argument("--key", required=False, default=os.getenv("MCP_AUTH_TOKEN", ""), help="Your User Auth Token")
    parser.add_argument("--dir", default=".", help="Workspace directory (default: current directory)")
    parser.add_argument("--root", default=None, help="Root folder containing all projects (e.g. C:\\projects)")
    parser.add_argument("--install-startup", action="store_true", help="Install to run silently in the background on Windows boot")
    parser.add_argument("--uninstall-startup", action="store_true", help="Remove from Windows startup")

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
        print("Specify --key <your-token> or run with --install-startup to register as a service.")
        sys.exit(1)

    agent = LocalBridgeAgent(server_url=args.server, auth_token=args.key, workspace_dir=args.dir, projects_root=args.root)
    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        print("\n👋 Disconnected.")


if __name__ == "__main__":
    main()
