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

# Initialize FastMCP Server
mcp_server = FastMCP(
    name="Antigravity IDE Remote Bridge",
    instructions="Connects web AI assistants to local VS Code and Antigravity IDE workspaces."
)
register_tools(mcp_server)

# Create FastMCP SSE application
sse_application = mcp_server.http_app(transport="sse")

# Initialize FastAPI Application with FastMCP lifespan
app = FastAPI(
    title="Antigravity IDE MCP Gateway",
    description="Multi-Tenant MCP & REST Bridge connecting Web LLMs to Local VS Code / Antigravity instances.",
    version="0.1.0",
    lifespan=sse_application.lifespan
)

# Enable CORS for browser-based AI clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount FastMCP SSE transport at /mcp
# Endpoints provided: /mcp/sse and /mcp/messages
app.mount("/mcp", sse_application)


class PollRequest(BaseModel):
    wait_timeout: float = 15.0


class GenerateTokenRequest(BaseModel):
    user_id: str


@app.get("/")
async def root():
    """Service status and quickstart information."""
    return {
        "service": "Antigravity IDE MCP Gateway",
        "version": "0.1.0",
        "status": "healthy",
        "mcp_sse_endpoint": "/mcp/sse",
        "mcp_messages_endpoint": "/mcp/messages",
        "documentation": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check for uptime monitors and container orchestrators."""
    return {"status": "ok", "timestamp": time.time()}


@app.get("/bridge.py")
async def get_bridge_script():
    """Serves the standalone local bridge runner so users can download it with zero git cloning."""
    bridge_file = Path(__file__).parent.parent / "bridge.py"
    if not bridge_file.exists():
        raise HTTPException(status_code=404, detail="bridge.py not found")
    with open(bridge_file, "r", encoding="utf-8") as f:
        content = f.read()
    return PlainTextResponse(content, media_type="text/x-python")



@app.api_route("/mcp", methods=["GET", "POST"])
async def mcp_redirect(request: Request):
    """Redirect /mcp to /mcp/sse, preserving query parameters and method."""
    query = str(request.url.query)
    target = "/mcp/sse"
    if query:
        target += f"?{query}"
    return RedirectResponse(url=target, status_code=307)


@app.api_route("/sse", methods=["GET", "POST"])
async def sse_redirect(request: Request):
    """Redirect /sse to /mcp/sse, preserving query parameters and method."""
    query = str(request.url.query)
    target = "/mcp/sse"
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


@app.post("/api/relay/poll")
async def relay_poll(
    payload: PollRequest = Body(default_factory=PollRequest),
    current_user: str = Depends(get_current_user)
):
    """
    Long-polling endpoint invoked by local IDE companion to receive queued tool executions.
    """
    task = await relay_manager.poll_task(user_id=current_user, wait_timeout=payload.wait_timeout)
    return {"task": task}


@app.post("/api/relay/result")
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


@app.post("/api/relay/heartbeat")
async def relay_heartbeat(current_user: str = Depends(get_current_user)):
    """Keepalive ping for local IDE companion."""
    relay_manager.update_heartbeat(current_user)
    return {"status": "alive", "user_id": current_user}


@app.post("/api/auth/generate-token")
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


@app.post("/api/tools/{tool_name}")
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
