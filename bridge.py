"""
Universal IDE & Developer Workspace - Standalone Global Multi-Project Bridge
Connects any project or IDE (VS Code, Cursor, Windsurf, JetBrains, Antigravity, Terminal)
to Gemini Web, ChatGPT, Claude via hosted MCP Gateway (Vercel).
Supports system-wide multi-project switching and background startup.
No git cloning required.
"""

import argparse
import asyncio
import fnmatch
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
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

    def create_directory(self, path: str, project: Optional[str] = None) -> Dict[str, Any]:
        target = self._resolve_safe_path(path, project=project)
        base_dir = (self.projects_root / project).resolve() if project else self.current_workspace_path
        target.mkdir(parents=True, exist_ok=True)
        return {
            "status": "success",
            "path": str(target.relative_to(base_dir)) if target != base_dir else ".",
            "full_path": str(target),
            "project": project or self.active_project,
            "message": f"Directory created successfully: {path}"
        }

    def delete_file(self, path: str, recursive: bool = False, project: Optional[str] = None) -> Dict[str, Any]:
        target = self._resolve_safe_path(path, project=project)
        base_dir = (self.projects_root / project).resolve() if project else self.current_workspace_path

        if target == self.projects_root or target == base_dir:
            raise PermissionError("Deleting the project root or workspace root is not permitted.")

        if not target.exists():
            raise FileNotFoundError(f"File or directory not found: {path}")

        rel_path = str(target.relative_to(base_dir))
        full_path = str(target)

        if target.is_dir():
            if recursive:
                shutil.rmtree(target)
            else:
                try:
                    target.rmdir()
                except OSError:
                    raise OSError(f"Directory is not empty: '{path}'. Set recursive=True to delete directory and all contents.")
            item_type = "directory"
        else:
            target.unlink()
            item_type = "file"

        return {
            "status": "success",
            "path": rel_path,
            "full_path": full_path,
            "project": project or self.active_project,
            "type": item_type,
            "message": f"Successfully deleted {item_type}: {path}"
        }

    def move_or_rename_file(self, source_path: str, destination_path: str, overwrite: bool = False, project: Optional[str] = None) -> Dict[str, Any]:
        src = self._resolve_safe_path(source_path, project=project)
        dest = self._resolve_safe_path(destination_path, project=project)
        base_dir = (self.projects_root / project).resolve() if project else self.current_workspace_path

        if not src.exists():
            raise FileNotFoundError(f"Source file or directory does not exist: {source_path}")

        if src == dest:
            return {
                "status": "noop",
                "message": "Source and destination are identical.",
                "path": str(src.relative_to(base_dir)),
                "full_path": str(src),
                "project": project or self.active_project
            }

        if dest.exists():
            if not overwrite:
                raise FileExistsError(f"Destination already exists: '{destination_path}'. Set overwrite=True to replace it.")
            if dest.is_dir():
                shutil.rmtree(dest)
            else:
                dest.unlink()

        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))

        return {
            "status": "success",
            "source_path": str(src.relative_to(base_dir)),
            "destination_path": str(dest.relative_to(base_dir)),
            "full_destination_path": str(dest),
            "project": project or self.active_project,
            "message": f"Successfully moved '{source_path}' to '{destination_path}'"
        }

    def get_file_info(self, path: str, project: Optional[str] = None) -> Dict[str, Any]:
        target = self._resolve_safe_path(path, project=project)
        base_dir = (self.projects_root / project).resolve() if project else self.current_workspace_path

        if not target.exists():
            return {
                "exists": False,
                "path": path,
                "full_path": str(target),
                "project": project or self.active_project
            }

        stat = target.stat()
        is_file = target.is_file()
        is_dir = target.is_dir()
        size_bytes = stat.st_size

        line_count = None
        if is_file and size_bytes < 10_000_000:
            try:
                with open(target, "r", encoding="utf-8", errors="ignore") as f:
                    line_count = sum(1 for _ in f)
            except Exception:
                pass

        created_time = datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat()
        modified_time = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

        return {
            "exists": True,
            "path": str(target.relative_to(base_dir)) if target != base_dir else ".",
            "full_path": str(target),
            "project": project or self.active_project,
            "type": "file" if is_file else ("directory" if is_dir else "other"),
            "size_bytes": size_bytes,
            "line_count": line_count,
            "extension": target.suffix if is_file else "",
            "modified_time": modified_time,
            "created_time": created_time
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

    DEV_SERVER_KEYWORDS = (
        "npm run dev", "npm start", "yarn dev", "yarn start", "pnpm dev", "pnpm start",
        "vite", "next dev", "uvicorn", "flask run", "python -m http.server"
    )

    def _is_dev_server_command(self, cmd: str) -> bool:
        clean = cmd.strip().lower()
        if clean.startswith("start "):
            return False
        return any(k in clean for k in self.DEV_SERVER_KEYWORDS)

    def _launch_background_server(self, command: str, cwd: Path, shell_type: str = "terminal", project: Optional[str] = None) -> Dict[str, Any]:
        proj_name = project or self.active_project or "Project"
        if sys.platform == "win32":
            subprocess.Popen(f'start "{proj_name} Dev Server" cmd.exe /k "{command}"', cwd=str(cwd), shell=True)
        else:
            subprocess.Popen(command, cwd=str(cwd), shell=True, start_new_session=True)

        return {
            "shell": shell_type,
            "command": command,
            "cwd": str(cwd),
            "exit_code": 0,
            "stdout": (
                f"✅ Dev server started in a new terminal window for '{proj_name}'.\n"
                f"Command: {command}\n"
                f"Directory: {cwd}\n"
                f"The server is now actively running in the background."
            ),
            "stderr": "",
            "status": "running_in_background"
        }

    def _run_process_safe(self, cmd_args, cwd: Path, timeout_seconds: int, shell: bool = False) -> Dict[str, Any]:
        """
        Executes a subprocess safely with process group isolation and guaranteed termination.
        On Windows, uses taskkill /F /T /PID to ensure all child processes are cleanly killed on timeout.
        """
        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

        try:
            proc = subprocess.Popen(
                cmd_args,
                cwd=str(cwd),
                shell=shell,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags
            )
            try:
                stdout, stderr = proc.communicate(timeout=timeout_seconds)
                return {
                    "exit_code": proc.returncode,
                    "stdout": stdout or "",
                    "stderr": stderr or ""
                }
            except subprocess.TimeoutExpired:
                if sys.platform == "win32":
                    try:
                        subprocess.run(
                            f"taskkill /F /T /PID {proc.pid}",
                            shell=True,
                            capture_output=True,
                            timeout=5
                        )
                    except Exception:
                        proc.kill()
                else:
                    proc.kill()
                try:
                    stdout, stderr = proc.communicate(timeout=2)
                except Exception:
                    stdout, stderr = "", ""
                return {
                    "exit_code": -1,
                    "stdout": stdout or "",
                    "stderr": f"Command timed out after {timeout_seconds}s and was terminated."
                }
        except Exception as e:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Execution failed: {str(e)}"
            }

    def execute_command(self, command: str, timeout_seconds: int = 30, project: Optional[str] = None) -> Dict[str, Any]:
        cwd = self._resolve_safe_path(".", project=project)
        if self._is_dev_server_command(command):
            return self._launch_background_server(command, cwd, shell_type="terminal", project=project)
        res = self._run_process_safe(command, cwd=cwd, timeout_seconds=timeout_seconds, shell=True)
        return {"command": command, "cwd": str(cwd), "exit_code": res["exit_code"], "stdout": res["stdout"], "stderr": res["stderr"]}

    def run_powershell(self, command: str, timeout_seconds: int = 60, project: Optional[str] = None) -> Dict[str, Any]:
        cwd = self._resolve_safe_path(".", project=project)
        if self._is_dev_server_command(command):
            return self._launch_background_server(command, cwd, shell_type="powershell", project=project)
        ps_bin = "powershell.exe" if sys.platform == "win32" else "pwsh"
        ps_cmd = [ps_bin, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", command]
        res = self._run_process_safe(ps_cmd, cwd=cwd, timeout_seconds=timeout_seconds, shell=False)
        return {"shell": "powershell", "command": command, "cwd": str(cwd), "exit_code": res["exit_code"], "stdout": res["stdout"], "stderr": res["stderr"]}

    def run_cmd(self, command: str, timeout_seconds: int = 60, project: Optional[str] = None) -> Dict[str, Any]:
        cwd = self._resolve_safe_path(".", project=project)
        if self._is_dev_server_command(command):
            return self._launch_background_server(command, cwd, shell_type="cmd", project=project)
        cmd_args = ["cmd.exe", "/c", command] if sys.platform == "win32" else ["sh", "-c", command]
        res = self._run_process_safe(cmd_args, cwd=cwd, timeout_seconds=timeout_seconds, shell=False)
        return {"shell": "cmd", "command": command, "cwd": str(cwd), "exit_code": res["exit_code"], "stdout": res["stdout"], "stderr": res["stderr"]}

    def run_git(self, subcommand: str, timeout_seconds: int = 60, project: Optional[str] = None) -> Dict[str, Any]:
        cwd = self._resolve_safe_path(".", project=project)
        full_command = f"git {subcommand}".strip()
        res = self._run_process_safe(full_command, cwd=cwd, timeout_seconds=timeout_seconds, shell=True)
        return {"git_command": full_command, "cwd": str(cwd), "exit_code": res["exit_code"], "stdout": res["stdout"], "stderr": res["stderr"]}

    def get_context(self) -> Dict[str, Any]:
        return self.get_active_project()


class LocalBridgeAgent:
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
        self.running = False

    def _execute_sync(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        p = parameters or {}

        def _get(*keys, default=None):
            for k in keys:
                if k in p and p[k] is not None:
                    return p[k]
            return default

        # Multi-Project Navigation
        if tool_name in ("list_projects", "get_projects"):
            return self.executor.list_projects()
        elif tool_name in ("set_active_project", "switch_project"):
            return self.executor.set_active_project(_get("project_name", "project", "name", default=""))
        elif tool_name in ("get_active_project", "current_project"):
            return self.executor.get_active_project()

        # Workspace Files & Directory Operations
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

        # Terminal & Shell Execution
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
            raise NotImplementedError(f"Tool '{tool_name}' is not recognized.")

    async def execute_task(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        """Runs the tool in an asynchronous worker thread to prevent blocking the event loop."""
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

    async def _poll_worker(self, worker_id: int, client: httpx.AsyncClient, poll_url: str, result_url: str):
        """Worker that polls cloud relay for tasks and submits results with retry."""
        consecutive_errors = 0
        while self.running:
            try:
                response = await client.post(poll_url, headers=self.headers, json={"wait_timeout": 1.5})
                if response.status_code == 401:
                    print("❌ Auth error: Token rejected by server. Exiting.")
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

                print(f"⚡ [AI REQUEST] {tool_name} -> {params}")
                result, error = None, None
                try:
                    result = await self.execute_task(tool_name, params)
                    print(f"✅ [SUCCESS] {tool_name}")
                except Exception as e:
                    error = str(e)
                    print(f"❌ [TOOL ERROR] {error}")

                # Retry submitting result for up to 26 seconds across Vercel serverless containers
                res_start = time.time()
                attempt = 0
                while (time.time() - res_start) < 26.0:
                    attempt += 1
                    try:
                        async with httpx.AsyncClient(timeout=4.0, limits=httpx.Limits(max_keepalive_connections=0)) as res_client:
                            res = await res_client.post(
                                result_url,
                                headers=self.headers,
                                json={"task_id": task_id, "result": result, "error": error}
                            )
                            if res.status_code == 200:
                                print(f"🚀 [RESULT DELIVERED] in {round(time.time() - res_start, 2)}s (attempt {attempt})")
                                break
                            elif attempt % 6 == 0:
                                print(f"⏳ [RESULT RETRY] attempt {attempt}: waiting for container (status {res.status_code})")
                    except Exception as e:
                        pass
                    await asyncio.sleep(0.25)

            except httpx.HTTPError:
                consecutive_errors += 1
                wait_time = min(5, 2 ** min(consecutive_errors, 2))
                await asyncio.sleep(wait_time)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(0.5)

    async def run(self):
        self.running = True
        print("=" * 60)
        print("🚀 Universal IDE Global Multi-Project Bridge Connected")
        print(f"📁 Projects Root:  {self.executor.projects_root}")
        if self.executor.active_project:
            print(f"🎯 Active Project: {self.executor.active_project}")
        print(f"🌐 Cloud Relay:    {self.server_url}")
        print("⚡ Engine:         High-Speed StreamableHTTP (3 Concurrent Workers)")
        print("=" * 60)
        print("Waiting for AI commands from Claude / Gemini / ChatGPT in browser...\n")

        poll_url = f"{self.server_url}/api/relay/poll"
        result_url = f"{self.server_url}/api/relay/result"

        limits = httpx.Limits(max_keepalive_connections=0, max_connections=20)
        async with httpx.AsyncClient(timeout=15.0, limits=limits) as client:
            keepalive_task = asyncio.create_task(self._keepalive_loop(client))
            workers = [
                asyncio.create_task(self._poll_worker(i, client, poll_url, result_url))
                for i in range(4)
            ]
            try:
                await asyncio.gather(*workers, return_exceptions=True)
            except asyncio.CancelledError:
                pass
            finally:
                self.running = False
                keepalive_task.cancel()
                for w in workers:
                    w.cancel()


def handle_startup_installation(server: str, key: str, root_dir: str, uninstall: bool = False):
    if sys.platform != "win32":
        print("Startup service installer is currently supported on Windows.")
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

    # Clean legacy if upgrading
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
    print(f"📁 Projects Root: {root_dir}")
    print(f"📍 Location:      {vbs_path}")
    print(f"⚡ It will now run silently in the background on every Windows boot.")
    print(f"=======================================================\n")


def main():
    parser = argparse.ArgumentParser(description="Universal IDE Standalone Global Multi-Project Bridge")
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
    while True:
        try:
            asyncio.run(agent.run())
        except KeyboardInterrupt:
            print("\n👋 Disconnected by user.")
            break
        except Exception as e:
            print(f"⚠️ Bridge connection interrupted ({e}). Auto-reconnecting in 3 seconds...")
            time.sleep(3)


if __name__ == "__main__":
    main()
