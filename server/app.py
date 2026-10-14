import time
from typing import Dict, Any, Optional
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, status, Body, Request
from fastapi.responses import RedirectResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastmcp import FastMCP

from server.auth import (
    get_current_user,
    verify_admin_key,
    generate_user_token,
    DYNAMIC_TOKENS
)
from server.relay import relay_manager, TaskResultSubmission
from server.tools import register_tools

from contextlib import asynccontextmanager, AsyncExitStack
from fastapi.responses import RedirectResponse, PlainTextResponse, JSONResponse

# Initialize FastMCP Server
mcp_server = FastMCP(
    name="Universal IDE Remote Bridge",
    instructions="Connects web AI assistants to local VS Code, Cursor, Windsurf, JetBrains, Antigravity, and any IDE workspace."
)
register_tools(mcp_server)

# 1. StreamableHTTP app (Required by Google Gemini Web Connected Apps & modern MCP clients)
streamable_http_app = mcp_server.http_app(path="/", stateless_http=True)

# 2. SSE app (For legacy SSE clients)
sse_application = mcp_server.http_app(transport="sse")

@asynccontextmanager
async def app_lifespan(fastapi_app: FastAPI):
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(streamable_http_app.lifespan(fastapi_app))
        await stack.enter_async_context(sse_application.lifespan(fastapi_app))
        yield

# Initialize FastAPI Application with combined FastMCP lifespan
app = FastAPI(
    title="Universal IDE MCP Gateway",
    description="Multi-Tenant MCP & REST Bridge connecting Web LLMs to any local IDE or developer workspace (VS Code, Cursor, Windsurf, JetBrains, etc.).",
    version="0.1.0",
    lifespan=app_lifespan
)

# Enable CORS for browser-based AI clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Probe & rewrite middleware: routes /mcp, /mcp/sse, and /sse without 404s or redirects
@app.middleware("http")
async def mcp_probe_middleware(request: Request, call_next):
    # Route SSE endpoints seamlessly whether client requests /mcp/sse, /sse, or /sse/sse
    if request.url.path in ("/mcp/sse", "/mcp/sse/"):
        request.scope["path"] = "/sse/sse"
        return await call_next(request)
    if request.url.path in ("/sse", "/sse/"):
        request.scope["path"] = "/sse/sse"
        return await call_next(request)
    # Route message endpoints with serverless fallback
    if request.method == "POST" and (
        request.url.path.startswith("/sse/messages") or request.url.path.startswith("/mcp/messages")
    ):
        try:
            transport = sse_application.routes[1].app.__self__
            session_id_param = request.query_params.get("session_id")
            from uuid import UUID
            sess_uuid = UUID(hex=session_id_param) if session_id_param else None
            has_session = sess_uuid in transport._read_stream_writers if sess_uuid else False
        except Exception:
            has_session = False

        if not has_session:
            # Serverless multi-instance fallback: route directly to StreamableHTTP (/mcp/)
            request.scope["path"] = "/mcp/"
            return await call_next(request)

        if request.url.path.startswith("/mcp/messages"):
            request.scope["path"] = request.url.path.replace("/mcp/messages", "/sse/messages")
        return await call_next(request)

    # Route StreamableHTTP endpoints seamlessly on /mcp
    if request.url.path in ("/mcp", "/mcp/"):
        if request.method in ("GET", "HEAD"):
            return JSONResponse({
                "status": "ok",
                "protocol": "model-context-protocol",
                "transport": "streamable-http",
                "server": "Universal IDE MCP Gateway"
            })
    if request.url.path == "/mcp":
        request.scope["path"] = "/mcp/"
    return await call_next(request)

# Mount StreamableHTTP at /mcp (Gemini Web Connected Apps connects directly to /mcp)
app.mount("/mcp", streamable_http_app)

# Mount SSE transport at /sse
app.mount("/sse", sse_application)


class PollRequest(BaseModel):
    wait_timeout: float = 15.0


class GenerateTokenRequest(BaseModel):
    user_id: str


@app.get("/")
async def root():
    """Service status and quickstart information."""
    return {
        "service": "Universal IDE MCP Gateway",
        "version": "0.1.0",
        "status": "healthy",
        "mcp_sse_endpoint": "/sse/sse",
        "mcp_streamable_endpoint": "/mcp",
        "documentation": "/docs"
    }


@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    """Health check endpoint to keep Vercel serverless function warm and monitor uptime."""
    return JSONResponse(
        content={
            "status": "ok",
            "service": "Universal IDE MCP Gateway",
            "timestamp": time.time()
        },
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate"
        }
    )


@app.get("/bridge.py")
async def get_bridge_script():
    """Serves the standalone local bridge runner so users can download it with zero git cloning."""
    bridge_file = Path(__file__).parent.parent / "bridge.py"
    if not bridge_file.exists():
        raise HTTPException(status_code=404, detail="bridge.py not found")
    with open(bridge_file, "r", encoding="utf-8") as f:
        content = f.read()
    return PlainTextResponse(content, media_type="text/x-python")



@app.api_route("/mcp/sse", methods=["GET", "POST"], include_in_schema=False)
async def mcp_sse_redirect(request: Request):
    """Redirect legacy /mcp/sse to /sse/sse, preserving query parameters."""
    query = str(request.url.query)
    target = "/sse/sse"
    if query:
        target += f"?{query}"
    return RedirectResponse(url=target, status_code=307)



@app.get("/api/status")
async def get_user_status(current_user: str = Depends(get_current_user)):
    """Check whether the authenticated user's local IDE companion is currently online."""
    online = relay_manager.is_client_online(current_user)
    last_seen = relay_manager.client_heartbeats.get(current_user)
    return {
        "user_id": current_user,
        "local_bridge_connected": online,
        "last_seen_seconds_ago": round(time.time() - last_seen, 1) if last_seen else None
    }


@app.post("/api/relay/poll", include_in_schema=False)
async def relay_poll(
    payload: PollRequest = Body(default_factory=PollRequest),
    current_user: str = Depends(get_current_user)
):
    """
    Long-polling endpoint invoked by local IDE companion to receive queued tool executions.
    """
    task = await relay_manager.poll_task(user_id=current_user, wait_timeout=payload.wait_timeout)
    return {"task": task}


@app.post("/api/relay/result", include_in_schema=False)
async def relay_result(
    submission: TaskResultSubmission,
    current_user: str = Depends(get_current_user)
):
    """
    Invoked by local IDE companion to report the execution result for a tool call.
    """
    success = await relay_manager.submit_result(
        task_id=submission.task_id,
        result=submission.result,
        error=submission.error
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task ID not found, expired, or already completed."
        )
    return {"status": "success", "task_id": submission.task_id}


@app.post("/api/relay/heartbeat", include_in_schema=False)
async def relay_heartbeat(current_user: str = Depends(get_current_user)):
    """Keepalive ping for local IDE companion."""
    relay_manager.update_heartbeat(current_user)
    return {"status": "alive", "user_id": current_user}


@app.post("/api/auth/generate-token", include_in_schema=False)
async def generate_token(
    payload: GenerateTokenRequest,
    is_admin: bool = Depends(verify_admin_key)
):
    """Admin-only endpoint to create a new user pairing token."""
    token = generate_user_token(payload.user_id)
    return {
        "status": "created",
        "user_id": payload.user_id,
        "token": token
    }


class ProjectNamePayload(BaseModel):
    project_name: str = ""

class ReadFilePayload(BaseModel):
    path: str
    max_lines: Optional[int] = 500
    start_line: Optional[int] = 1
    project: Optional[str] = None

class WriteFilePayload(BaseModel):
    path: str
    content: str
    project: Optional[str] = None

class EditFilePayload(BaseModel):
    path: str
    old_str: str
    new_str: str
    project: Optional[str] = None

class CreateDirPayload(BaseModel):
    path: str
    project: Optional[str] = None

class DeleteFilePayload(BaseModel):
    path: str
    recursive: Optional[bool] = False
    project: Optional[str] = None

class MoveFilePayload(BaseModel):
    source_path: str
    destination_path: str
    overwrite: Optional[bool] = False
    project: Optional[str] = None

class FilePathPayload(BaseModel):
    path: str
    project: Optional[str] = None

class ListDirPayload(BaseModel):
    path: Optional[str] = "."
    max_depth: Optional[int] = 2
    project: Optional[str] = None

class SearchFilesPayload(BaseModel):
    query: str
    path: Optional[str] = "."
    file_pattern: Optional[str] = "*"
    project: Optional[str] = None

class CommandPayload(BaseModel):
    command: str
    timeout_seconds: Optional[int] = 60
    project: Optional[str] = None

class GitPayload(BaseModel):
    subcommand: str
    timeout_seconds: Optional[int] = 60
    project: Optional[str] = None


@app.post("/api/tools/{tool_name}", include_in_schema=False)
async def execute_tool_direct(
    tool_name: str,
    parameters: Dict[str, Any] = Body(default_factory=dict),
    current_user: str = Depends(get_current_user)
):
    """
    Direct REST API to execute any tool on the user's local IDE.
    Useful for ChatGPT Custom GPT Actions, curl, or standard HTTP webhooks.
    """
    try:
        result = await relay_manager.dispatch_task(
            user_id=current_user,
            tool_name=tool_name,
            parameters=parameters
        )
        return {"status": "success", "tool": tool_name, "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------------------------------------------------------------------------
# Explicit REST Action Endpoints for ChatGPT Web Custom Actions
# -------------------------------------------------------------------------

@app.post("/api/action/list_projects", summary="List all projects on user computer")
async def action_list_projects(current_user: str = Depends(get_current_user)):
    return await relay_manager.dispatch_task(user_id=current_user, tool_name="list_projects", parameters={})

@app.post("/api/action/set_active_project", summary="Switch active project context")
async def action_set_active_project(payload: ProjectNamePayload, current_user: str = Depends(get_current_user)):
    return await relay_manager.dispatch_task(user_id=current_user, tool_name="set_active_project", parameters=payload.model_dump())

@app.post("/api/action/get_active_project", summary="Get active project status and path")
async def action_get_active_project(current_user: str = Depends(get_current_user)):
    return await relay_manager.dispatch_task(user_id=current_user, tool_name="get_active_project", parameters={})

@app.post("/api/action/get_workspace_context", summary="Get workspace overview and git status")
async def action_get_workspace_context(current_user: str = Depends(get_current_user)):
    return await relay_manager.dispatch_task(user_id=current_user, tool_name="get_workspace_context", parameters={})

@app.post("/api/action/read_workspace_file", summary="Read lines from a workspace file")
async def action_read_file(payload: ReadFilePayload, current_user: str = Depends(get_current_user)):
    return await relay_manager.dispatch_task(user_id=current_user, tool_name="read_workspace_file", parameters=payload.model_dump())

@app.post("/api/action/write_workspace_file", summary="Create or overwrite a file")
async def action_write_file(payload: WriteFilePayload, current_user: str = Depends(get_current_user)):
    return await relay_manager.dispatch_task(user_id=current_user, tool_name="write_workspace_file", parameters=payload.model_dump())

@app.post("/api/action/edit_workspace_file", summary="Replace text in a workspace file")
async def action_edit_file(payload: EditFilePayload, current_user: str = Depends(get_current_user)):
    return await relay_manager.dispatch_task(user_id=current_user, tool_name="edit_workspace_file", parameters=payload.model_dump())

@app.post("/api/action/create_directory", summary="Create a new directory or folder")
async def action_create_dir(payload: CreateDirPayload, current_user: str = Depends(get_current_user)):
    return await relay_manager.dispatch_task(user_id=current_user, tool_name="create_directory", parameters=payload.model_dump())

@app.post("/api/action/delete_file", summary="Delete a file or directory")
async def action_delete_file(payload: DeleteFilePayload, current_user: str = Depends(get_current_user)):
    return await relay_manager.dispatch_task(user_id=current_user, tool_name="delete_file", parameters=payload.model_dump())

@app.post("/api/action/move_or_rename_file", summary="Move or rename a file or directory")
async def action_move_file(payload: MoveFilePayload, current_user: str = Depends(get_current_user)):
    return await relay_manager.dispatch_task(user_id=current_user, tool_name="move_or_rename_file", parameters=payload.model_dump())

@app.post("/api/action/get_file_info", summary="Get metadata, size, timestamps, and line count")
async def action_get_file_info(payload: FilePathPayload, current_user: str = Depends(get_current_user)):
    return await relay_manager.dispatch_task(user_id=current_user, tool_name="get_file_info", parameters=payload.model_dump())

@app.post("/api/action/list_workspace_directory", summary="List files and folders in directory")
async def action_list_dir(payload: ListDirPayload, current_user: str = Depends(get_current_user)):
    return await relay_manager.dispatch_task(user_id=current_user, tool_name="list_workspace_directory", parameters=payload.model_dump())

@app.post("/api/action/search_workspace_files", summary="Search text across files")
async def action_search_files(payload: SearchFilesPayload, current_user: str = Depends(get_current_user)):
    return await relay_manager.dispatch_task(user_id=current_user, tool_name="search_workspace_files", parameters=payload.model_dump())

@app.post("/api/action/run_powershell_command", summary="Execute PowerShell command or script")
async def action_run_powershell(payload: CommandPayload, current_user: str = Depends(get_current_user)):
    return await relay_manager.dispatch_task(user_id=current_user, tool_name="run_powershell_command", parameters=payload.model_dump())

@app.post("/api/action/run_cmd_command", summary="Execute Command Prompt cmd.exe command")
async def action_run_cmd(payload: CommandPayload, current_user: str = Depends(get_current_user)):
    return await relay_manager.dispatch_task(user_id=current_user, tool_name="run_cmd_command", parameters=payload.model_dump())

@app.post("/api/action/run_git_command", summary="Execute Git command")
async def action_run_git(payload: GitPayload, current_user: str = Depends(get_current_user)):
    return await relay_manager.dispatch_task(user_id=current_user, tool_name="run_git_command", parameters=payload.model_dump())

@app.post("/api/action/run_terminal_command", summary="Execute general terminal command")
async def action_run_terminal(payload: CommandPayload, current_user: str = Depends(get_current_user)):
    return await relay_manager.dispatch_task(user_id=current_user, tool_name="run_terminal_command", parameters=payload.model_dump())

