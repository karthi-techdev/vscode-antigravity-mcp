"""
Antigravity IDE - Standalone Local Bridge
Connects any local project folder to your hosted MCP Gateway (Vercel).
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
    """Executes file operations and commands safely inside the workspace directory."""
    def __init__(self, workspace_dir: str = "."):
        self.workspace_path = Path(workspace_dir).resolve()
        if not self.workspace_path.exists():
            self.workspace_path.mkdir(parents=True, exist_ok=True)

    def _resolve_safe_path(self, relative_or_abs_path: str) -> Path:
        target = (self.workspace_path / relative_or_abs_path).resolve()
        try:
            target.relative_to(self.workspace_path)
        except ValueError:
            raise PermissionError(
                f"Access denied: '{relative_or_abs_path}' is outside authorized workspace '{self.workspace_path}'"
            )
        return target

    def read_file(self, path: str, max_lines: Optional[int] = 500, start_line: int = 1) -> Dict[str, Any]:
        target = self._resolve_safe_path(path)
        if not target.is_file():
            raise FileNotFoundError(f"File not found: {path}")

        with open(target, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

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
        target = self._resolve_safe_path(path)
        if not target.is_file():
            raise FileNotFoundError(f"File not found: {path}")

        with open(target, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        if old_str not in content:
            raise ValueError(f"Target pattern not found in {path}")

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
        target = self._resolve_safe_path(path)
        if not target.is_dir():
            raise NotADirectoryError(f"Directory not found: {path}")

        results: List[Dict[str, Any]] = []
        ignored_dirs = {".git", ".venv", "venv", "__pycache__", "node_modules", ".vercel"}

        for root, dirs, files in os.walk(target):
            dirs[:] = [d for d in dirs if d not in ignored_dirs]
            rel_root = Path(root).relative_to(self.workspace_path)
            depth = len(rel_root.parts)

            if depth > max_depth:
                dirs.clear()
                continue

            for d in sorted(dirs):
                item_path = Path(root) / d
                results.append({"name": d, "path": str(item_path.relative_to(self.workspace_path)), "type": "directory"})

            for f in sorted(files):
                item_path = Path(root) / f
                try:
                    size = item_path.stat().st_size
                except OSError:
                    size = 0
                results.append({"name": f, "path": str(item_path.relative_to(self.workspace_path)), "type": "file", "size_bytes": size})

        return {
            "workspace_root": str(self.workspace_path),
            "directory": str(target.relative_to(self.workspace_path)) if target != self.workspace_path else ".",
            "entries_count": len(results),
            "entries": results
        }

    def search_files(self, query: str, path: str = ".", file_pattern: str = "*") -> Dict[str, Any]:
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

        return {"query": query, "matches_found": len(matches), "matches": matches}

    def execute_command(self, command: str, timeout_seconds: int = 30) -> Dict[str, Any]:
        try:
            res = subprocess.run(
                command,
                cwd=str(self.workspace_path),
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_seconds
            )
            return {"command": command, "exit_code": res.returncode, "stdout": res.stdout, "stderr": res.stderr}
        except subprocess.TimeoutExpired:
            return {"command": command, "exit_code": -1, "stdout": "", "stderr": f"Command timed out after {timeout_seconds}s"}
        except Exception as e:
            return {"command": command, "exit_code": -1, "stdout": "", "stderr": f"Execution failed: {str(e)}"}

    def get_context(self) -> Dict[str, Any]:
        git_branch, git_status = None, None
        try:
            res = subprocess.run("git rev-parse --abbrev-ref HEAD", cwd=str(self.workspace_path), shell=True, capture_output=True, text=True, timeout=3)
            if res.returncode == 0:
                git_branch = res.stdout.strip()
            status_res = subprocess.run("git status --short", cwd=str(self.workspace_path), shell=True, capture_output=True, text=True, timeout=3)
            if status_res.returncode == 0:
                git_status = status_res.stdout.strip()
        except Exception:
            pass
        return {"workspace_path": str(self.workspace_path), "git_branch": git_branch, "git_status": git_status}


class LocalBridgeAgent:
    def __init__(self, server_url: str, auth_token: str, workspace_dir: str = "."):
        self.server_url = server_url.rstrip("/")
        self.auth_token = auth_token
        self.workspace_dir = workspace_dir
        self.executor = LocalIDEExecutor(workspace_dir=workspace_dir)
        self.headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "User-Agent": "Antigravity-Bridge/1.0",
            "Content-Type": "application/json"
        }
        self.running = False

    async def execute_task(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        p = parameters or {}
        if tool_name in ("read_workspace_file", "read_file"):
            return self.executor.read_file(p.get("path", ""), p.get("max_lines", 500), p.get("start_line", 1))
        elif tool_name in ("write_workspace_file", "write_file"):
            return self.executor.write_file(p.get("path", ""), p.get("content", ""))
        elif tool_name in ("edit_workspace_file", "edit_file"):
            return self.executor.edit_file(p.get("path", ""), p.get("old_str", ""), p.get("new_str", ""))
        elif tool_name in ("list_workspace_directory", "list_directory"):
            return self.executor.list_directory(p.get("path", "."), p.get("max_depth", 2))
        elif tool_name in ("search_workspace_files", "search_files"):
            return self.executor.search_files(p.get("query", ""), p.get("path", "."), p.get("file_pattern", "*"))
        elif tool_name in ("run_terminal_command", "execute_command"):
            return self.executor.execute_command(p.get("command", ""), p.get("timeout_seconds", 30))
        elif tool_name in ("get_workspace_context", "get_context"):
            return self.executor.get_context()
        else:
            raise NotImplementedError(f"Tool '{tool_name}' is not recognized.")

    async def run(self):
        self.running = True
        print("=" * 60)
        print("🚀 Antigravity IDE Bridge Connected")
        print(f"📁 Workspace:  {self.executor.workspace_path}")
        print(f"🌐 Cloud Relay: {self.server_url}")
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


def main():
    parser = argparse.ArgumentParser(description="Antigravity IDE Standalone Bridge")
    parser.add_argument("--server", required=True, help="Cloud MCP Server URL (e.g. https://your-domain.vercel.app)")
    parser.add_argument("--key", required=True, help="Your User Auth Token")
    parser.add_argument("--dir", default=".", help="Workspace directory to connect (default: current directory)")

    args = parser.parse_args()
    agent = LocalBridgeAgent(server_url=args.server, auth_token=args.key, workspace_dir=args.dir)
    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        print("\n👋 Disconnected.")


if __name__ == "__main__":
    main()
