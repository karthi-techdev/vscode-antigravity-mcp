import os
import sys
import subprocess
import fnmatch
from pathlib import Path
from typing import Dict, Any, List, Optional


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
            # If target_dir is a project inside a projects directory (e.g. C:\projects\my-app),
            # allow its parent to be the projects_root if common patterns match
            if target_dir.parent.exists() and target_dir.parent.name in ("projects", "workspace", "repos", "code", "dev"):
                self.projects_root = target_dir.parent
            else:
                self.projects_root = target_dir

        if not self.projects_root.exists():
            self.projects_root.mkdir(parents=True, exist_ok=True)

        # If target_dir is inside projects_root and not the root itself, make it active
        if target_dir != self.projects_root and self.projects_root in target_dir.parents:
            self.active_project: Optional[str] = str(target_dir.relative_to(self.projects_root))
        else:
            self.active_project = None

    @property
    def current_workspace_path(self) -> Path:
        """Returns the currently active workspace directory."""
        if self.active_project:
            return (self.projects_root / self.active_project).resolve()
        return self.projects_root

    def list_projects(self) -> Dict[str, Any]:
        """
        Discover and list all project folders on the local machine under projects_root.
        Identifies tech stack and Git branches where available.
        """
        projects: List[Dict[str, Any]] = []
        ignored = {".git", ".venv", "venv", "__pycache__", "node_modules", ".vercel", "$RECYCLE.BIN"}

        if self.projects_root.is_dir():
            for entry in sorted(self.projects_root.iterdir()):
                if entry.is_dir() and entry.name not in ignored:
                    # Detect project type
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

                    # Check git branch if git repo
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
        """Switch the current working project context."""
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
        """Get details about the currently selected active project."""
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
        """Resolve a file path, ensuring it stays within the designated project or projects_root."""
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
        """Read lines from a workspace file."""
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
        """Write or overwrite content to a file inside the workspace."""
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
        """Replace exact occurrences of text inside a file."""
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
        """List files and directories within a workspace directory."""
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
                results.append({
                    "name": d,
                    "path": str(item_path.relative_to(base_dir)),
                    "type": "directory"
                })

            for f in sorted(files):
                item_path = Path(root) / f
                try:
                    size = item_path.stat().st_size
                except OSError:
                    size = 0
                results.append({
                    "name": f,
                    "path": str(item_path.relative_to(base_dir)),
                    "type": "file",
                    "size_bytes": size
                })

        return {
            "workspace_root": str(base_dir),
            "project": project or self.active_project,
            "directory": str(target.relative_to(base_dir)) if target != base_dir else ".",
            "entries_count": len(results),
            "entries": results
        }

    def search_files(self, query: str, path: str = ".", file_pattern: str = "*", project: Optional[str] = None) -> Dict[str, Any]:
        """Search for a text query inside files within the workspace."""
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

        return {
            "query": query,
            "workspace": str(self.current_workspace_path),
            "matches_found": len(matches),
            "matches": matches
        }

    def execute_command(self, command: str, timeout_seconds: int = 30, project: Optional[str] = None) -> Dict[str, Any]:
        """Execute a shell command inside the active project directory."""
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
            return {
                "command": command,
                "cwd": str(cwd),
                "exit_code": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr
            }
        except subprocess.TimeoutExpired:
            return {
                "command": command,
                "cwd": str(cwd),
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Command timed out after {timeout_seconds} seconds"
            }
        except Exception as e:
            return {
                "command": command,
                "cwd": str(cwd),
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Execution failed: {str(e)}"
            }

    def run_powershell(self, command: str, timeout_seconds: int = 60, project: Optional[str] = None) -> Dict[str, Any]:
        """Execute a PowerShell command with full PowerShell environment and UTF-8 encoding."""
        cwd = self._resolve_safe_path(".", project=project)
        ps_bin = "powershell.exe" if sys.platform == "win32" else "pwsh"
        ps_cmd = [
            ps_bin,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy", "Bypass",
            "-Command", command
        ]
        try:
            res = subprocess.run(
                ps_cmd,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds
            )
            return {
                "shell": "powershell",
                "command": command,
                "cwd": str(cwd),
                "exit_code": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr
            }
        except subprocess.TimeoutExpired:
            return {
                "shell": "powershell",
                "command": command,
                "cwd": str(cwd),
                "exit_code": -1,
                "stdout": "",
                "stderr": f"PowerShell command timed out after {timeout_seconds} seconds"
            }
        except Exception as e:
            return {
                "shell": "powershell",
                "command": command,
                "cwd": str(cwd),
                "exit_code": -1,
                "stdout": "",
                "stderr": f"PowerShell execution failed: {str(e)}"
            }

    def run_cmd(self, command: str, timeout_seconds: int = 60, project: Optional[str] = None) -> Dict[str, Any]:
        """Execute a Command Prompt (cmd.exe) command."""
        cwd = self._resolve_safe_path(".", project=project)
        cmd_args = ["cmd.exe", "/c", command] if sys.platform == "win32" else ["sh", "-c", command]
        try:
            res = subprocess.run(
                cmd_args,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds
            )
            return {
                "shell": "cmd",
                "command": command,
                "cwd": str(cwd),
                "exit_code": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr
            }
        except subprocess.TimeoutExpired:
            return {
                "shell": "cmd",
                "command": command,
                "cwd": str(cwd),
                "exit_code": -1,
                "stdout": "",
                "stderr": f"CMD command timed out after {timeout_seconds} seconds"
            }
        except Exception as e:
            return {
                "shell": "cmd",
                "command": command,
                "cwd": str(cwd),
                "exit_code": -1,
                "stdout": "",
                "stderr": f"CMD execution failed: {str(e)}"
            }

    def run_git(self, subcommand: str, timeout_seconds: int = 60, project: Optional[str] = None) -> Dict[str, Any]:
        """Execute a Git command in the active or specified project directory."""
        cwd = self._resolve_safe_path(".", project=project)
        full_command = f"git {subcommand}".strip()
        try:
            res = subprocess.run(
                full_command,
                cwd=str(cwd),
                shell=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds
            )
            return {
                "git_command": full_command,
                "cwd": str(cwd),
                "exit_code": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr
            }
        except subprocess.TimeoutExpired:
            return {
                "git_command": full_command,
                "cwd": str(cwd),
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Git command timed out after {timeout_seconds} seconds"
            }
        except Exception as e:
            return {
                "git_command": full_command,
                "cwd": str(cwd),
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Git execution failed: {str(e)}"
            }

    def get_context(self) -> Dict[str, Any]:
        """Get high-level summary of active project and git status."""
        return self.get_active_project()
