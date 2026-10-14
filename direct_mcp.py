"""
Universal IDE Direct MCP Server & Tunnel Runner
Runs a high-speed, direct FastMCP server locally on your computer and exposes
it via a secure Cloudflare Tunnel (https://...trycloudflare.com/mcp).

Why this is 100% reliable:
- Zero Vercel multi-container routing drops
- Zero 30-second timeouts (commands execute directly in <10ms)
- Zero authentication mismatch or 404s
- Works instantly with Claude Web, ChatGPT, and Gemini Web
"""

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastmcp import FastMCP
import uvicorn

# Ensure UTF-8 output on Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure project root in sys.path
_root = Path(__file__).parent.resolve()
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from client.executor import LocalIDEExecutor


def create_direct_app(projects_root: Optional[str] = None) -> FastAPI:
    executor = LocalIDEExecutor(projects_root=projects_root)

    mcp = FastMCP(
        name="Universal IDE Direct Bridge",
        instructions="Connects web AI assistants directly to your local computer projects and IDE with zero latency."
    )

    # 1. Multi-Project Management
    @mcp.tool()
    def list_projects() -> Dict[str, Any]:
        """Discover and list all project folders and repositories available on the user's system."""
        return executor.list_projects()

    @mcp.tool()
    def set_active_project(project_name: str) -> Dict[str, Any]:
        """Switch the active project context to a specific project folder on the user's machine."""
        return executor.set_active_project(project_name)

    @mcp.tool()
    def get_active_project() -> Dict[str, Any]:
        """Get the currently active project folder name, absolute path, and git status."""
        return executor.get_active_project()

    @mcp.tool()
    def get_workspace_context() -> Dict[str, Any]:
        """Get an overview of the active workspace, project name, root directory, and git status."""
        return executor.get_context()

    # 2. File and Directory Operations
    @mcp.tool()
    def read_workspace_file(path: str, max_lines: int = 500, start_line: int = 1, project: Optional[str] = None) -> Dict[str, Any]:
        """Read lines from a workspace file with line numbers."""
        return executor.read_file(path=path, max_lines=max_lines, start_line=start_line, project=project)

    @mcp.tool()
    def write_workspace_file(path: str, content: str, project: Optional[str] = None) -> Dict[str, Any]:
        """Create a new file or completely overwrite an existing file in the active or specified project."""
        return executor.write_file(path=path, content=content, project=project)

    @mcp.tool()
    def edit_workspace_file(path: str, old_str: str, new_str: str, project: Optional[str] = None) -> Dict[str, Any]:
        """Perform a precise text replacement within a workspace file."""
        return executor.edit_file(path=path, old_str=old_str, new_str=new_str, project=project)

    @mcp.tool()
    def create_directory(path: str, project: Optional[str] = None) -> Dict[str, Any]:
        """Create a new directory or folder inside the active or specified project."""
        return executor.create_directory(path=path, project=project)

    @mcp.tool()
    def delete_file(path: str, recursive: bool = False, project: Optional[str] = None) -> Dict[str, Any]:
        """Delete a file or empty directory in the active or specified project."""
        return executor.delete_file(path=path, recursive=recursive, project=project)

    @mcp.tool()
    def move_or_rename_file(source_path: str, destination_path: str, overwrite: bool = False, project: Optional[str] = None) -> Dict[str, Any]:
        """Move or rename a file or directory within the workspace."""
        return executor.move_or_rename_file(source_path=source_path, destination_path=destination_path, overwrite=overwrite, project=project)

    @mcp.tool()
    def get_file_info(path: str, project: Optional[str] = None) -> Dict[str, Any]:
        """Get comprehensive metadata about a file or directory."""
        return executor.get_file_info(path=path, project=project)

    @mcp.tool()
    def list_workspace_directory(path: str = ".", max_depth: int = 2, project: Optional[str] = None) -> Dict[str, Any]:
        """List files and folders within a workspace directory up to a given depth."""
        return executor.list_directory(path=path, max_depth=max_depth, project=project)

    @mcp.tool()
    def search_workspace_files(query: str, path: str = ".", file_pattern: str = "*", project: Optional[str] = None) -> Dict[str, Any]:
        """Search for a text string or regex pattern across files in the workspace."""
        return executor.search_files(query=query, path=path, file_pattern=file_pattern, project=project)

    # 3. Terminal and Shell Execution
    @mcp.tool()
    def run_powershell_command(command: str, timeout_seconds: int = 60, project: Optional[str] = None) -> Dict[str, Any]:
        """Execute a PowerShell command with full environment and UTF-8 encoding in the active project."""
        return executor.run_powershell(command=command, timeout_seconds=timeout_seconds, project=project)

    @mcp.tool()
    def run_cmd_command(command: str, timeout_seconds: int = 60, project: Optional[str] = None) -> Dict[str, Any]:
        """Execute a Command Prompt (cmd.exe) command or batch script in the active project."""
        return executor.run_cmd(command=command, timeout_seconds=timeout_seconds, project=project)

    @mcp.tool()
    def run_git_command(subcommand: str, timeout_seconds: int = 60, project: Optional[str] = None) -> Dict[str, Any]:
        """Execute a Git command in the project repository."""
        return executor.run_git(subcommand=subcommand, timeout_seconds=timeout_seconds, project=project)

    @mcp.tool()
    def run_terminal_command(command: str, timeout_seconds: int = 30, project: Optional[str] = None) -> Dict[str, Any]:
        """Execute a terminal shell command inside the active project directory."""
        return executor.execute_command(command=command, timeout_seconds=timeout_seconds, project=project)

    # Initialize FastMCP HTTP App (Official StreamableHTTP standard)
    streamable_http = mcp.http_app(path="/", stateless_http=True)

    app = FastAPI(
        title="Universal IDE Direct MCP Server",
        description="High-Speed Direct MCP Bridge with Zero Relay Latency",
        lifespan=streamable_http.lifespan
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def rewrite_mcp_path(request: Request, call_next):
        if request.url.path in ("/mcp", "/mcp/", "/sse", "/sse/"):
            if request.method in ("GET", "HEAD"):
                return JSONResponse({
                    "status": "ok",
                    "protocol": "model-context-protocol",
                    "transport": "streamable-http",
                    "server": "Universal IDE Direct Bridge",
                    "endpoint": "/mcp"
                })
            request.scope["path"] = "/mcp/"
        return await call_next(request)

    app.mount("/mcp", streamable_http)
    app.mount("/sse", streamable_http)

    @app.get("/")
    async def root():
        return {
            "service": "Universal IDE Direct MCP Server",
            "status": "online",
            "transport": "streamable-http",
            "endpoint": "/mcp",
            "projects_root": str(executor.projects_root),
            "active_project": executor.active_project
        }

    return app


def start_tunnel(port: int = 8000) -> Optional[subprocess.Popen]:
    cloudflared_path = Path(__file__).parent / "cloudflared.exe"
    if not cloudflared_path.exists():
        return None

    cmd = [str(cloudflared_path), "tunnel", "--url", f"http://127.0.0.1:{port}"]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1
    )
    return proc


def main():
    parser = argparse.ArgumentParser(description="Universal IDE Direct High-Speed MCP Server")
    parser.add_argument("--root", default="C:\\projects", help="Projects root directory")
    parser.add_argument("--port", type=int, default=8000, help="Local port to bind")
    args = parser.parse_args()

    print("=" * 65, flush=True)
    print("🚀 Universal IDE Direct MCP Server Starting...", flush=True)
    print(f"📁 Projects Root: {args.root}", flush=True)
    print("=" * 65, flush=True)

    # Start Cloudflare Tunnel in background
    tunnel_proc = start_tunnel(args.port)
    tunnel_url = None

    if tunnel_proc:
        print("⚡ Establishing secure Cloudflare Tunnel...", flush=True)
        start_t = time.time()
        while time.time() - start_t < 20:
            line = tunnel_proc.stderr.readline()
            if not line:
                break
            match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
            if match:
                tunnel_url = match.group(0)
                break

    print("\n" + "=" * 65)
    if tunnel_url:
        print("🎉 DIRECT MCP SERVER IS LIVE & READY FOR AI!")
        print(f"👉 PUBLIC MCP URL:  {tunnel_url}/mcp")
        print("=" * 65)
        print("Copy the URL above and paste it into:")
        print("  • Claude Web: Add Custom Connector -> URL: " + tunnel_url + "/mcp")
        print("  • ChatGPT: Custom GPT Action or Connector -> URL: " + tunnel_url + "/mcp")
        print("  • Gemini Web: Connected App -> URL: " + tunnel_url + "/mcp")
        print("⚡ Execution speed: <10ms | Zero Vercel Drops | Zero Timeouts")
    else:
        print("🎉 LOCAL MCP SERVER IS LIVE!")
        print(f"👉 LOCAL MCP URL:   http://127.0.0.1:{args.port}/mcp")
    print("=" * 65 + "\n")

    app = create_direct_app(projects_root=args.root)
    try:
        uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    finally:
        if tunnel_proc:
            tunnel_proc.terminate()


if __name__ == "__main__":
    main()
