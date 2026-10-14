import os
import subprocess
import fnmatch
from pathlib import Path
from typing import Dict, Any, List, Optional


class LocalIDEExecutor:
    """
    Executes actions inside the local user's workspace directory.
    Enforces path scoping to prevent directory traversal outside the workspace.
    """
    def __init__(self, workspace_dir: str = "."):
        self.workspace_path = Path(workspace_dir).resolve()
        if not self.workspace_path.exists():
            self.workspace_path.mkdir(parents=True, exist_ok=True)

    def _resolve_safe_path(self, relative_or_abs_path: str) -> Path:
        """Resolve a path and ensure it stays within the designated workspace directory."""
        target = (self.workspace_path / relative_or_abs_path).resolve()
        try:
            target.relative_to(self.workspace_path)
        except ValueError:
            raise PermissionError(
                f"Access denied: '{relative_or_abs_path}' is outside the authorized workspace '{self.workspace_path}'"
            )
        return target

    def read_file(self, path: str, max_lines: Optional[int] = 500, start_line: int = 1) -> Dict[str, Any]:
        """Read lines from a workspace file."""
        target = self._resolve_safe_path(path)
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
            "path": str(target.relative_to(self.workspace_path)),
            "total_lines": total_lines,
            "start_line": start_line,
            "returned_lines": len(selected_lines),
            "content": content_with_numbers,
            "raw_content": "".join(selected_lines)
        }

    def write_file(self, path: str, content: str) -> Dict[str, Any]:
        """Write or overwrite content to a file inside the workspace."""
        target = self._resolve_safe_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)

        with open(target, "w", encoding="utf-8") as f:
            f.write(content)

        return {
            "status": "success",
            "path": str(target.relative_to(self.workspace_path)),
            "bytes_written": len(content.encode("utf-8"))
        }

    def edit_file(self, path: str, old_str: str, new_str: str) -> Dict[str, Any]:
        """Replace exact occurrences of text inside a file."""
        target = self._resolve_safe_path(path)
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
            "path": str(target.relative_to(self.workspace_path)),
            "replacements_made": count
        }

    def list_directory(self, path: str = ".", max_depth: int = 2) -> Dict[str, Any]:
        """List files and directories within a workspace directory."""
        target = self._resolve_safe_path(path)
        if not target.is_dir():
            raise NotADirectoryError(f"Directory not found: {path}")

        results: List[Dict[str, Any]] = []
        ignored_dirs = {".git", ".venv", "venv", "__pycache__", "node_modules", ".vercel"}

        for root, dirs, files in os.walk(target):
            # Prune ignored directories
            dirs[:] = [d for d in dirs if d not in ignored_dirs]
            rel_root = Path(root).relative_to(self.workspace_path)
            depth = len(rel_root.parts)

            if depth > max_depth:
                dirs.clear()
                continue

            for d in sorted(dirs):
                item_path = Path(root) / d
                results.append({
                    "name": d,
                    "path": str(item_path.relative_to(self.workspace_path)),
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
                    "path": str(item_path.relative_to(self.workspace_path)),
                    "type": "file",
                    "size_bytes": size
                })

        return {
            "workspace_root": str(self.workspace_path),
            "directory": str(target.relative_to(self.workspace_path)) if target != self.workspace_path else ".",
            "entries_count": len(results),
            "entries": results
        }

    def search_files(self, query: str, path: str = ".", file_pattern: str = "*") -> Dict[str, Any]:
        """Search for a text query inside files within the workspace."""
        target = self._resolve_safe_path(path)
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
                                    "file": str(file_path.relative_to(self.workspace_path)),
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
            "matches_found": len(matches),
            "matches": matches
        }

    def execute_command(self, command: str, timeout_seconds: int = 30) -> Dict[str, Any]:
        """
        Execute a shell command inside the workspace directory.
        """
        try:
            res = subprocess.run(
                command,
                cwd=str(self.workspace_path),
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_seconds
            )
            return {
                "command": command,
                "exit_code": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr
            }
        except subprocess.TimeoutExpired:
            return {
                "command": command,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Command timed out after {timeout_seconds} seconds"
            }
        except Exception as e:
            return {
                "command": command,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Execution failed: {str(e)}"
            }

    def get_context(self) -> Dict[str, Any]:
        """Get high-level summary of the workspace and git status."""
        git_branch = None
        git_status = None
        try:
            res = subprocess.run(
                "git rev-parse --abbrev-ref HEAD",
                cwd=str(self.workspace_path),
                shell=True,
                capture_output=True,
                text=True,
                timeout=3
            )
            if res.returncode == 0:
                git_branch = res.stdout.strip()
            
            status_res = subprocess.run(
                "git status --short",
                cwd=str(self.workspace_path),
                shell=True,
                capture_output=True,
                text=True,
                timeout=3
            )
            if status_res.returncode == 0:
                git_status = status_res.stdout.strip()
        except Exception:
            pass

        return {
            "workspace_path": str(self.workspace_path),
            "git_branch": git_branch,
            "git_status": git_status
        }
