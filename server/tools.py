from typing import Optional, Dict, Any
from fastmcp import FastMCP
from server.auth import verify_token
from server.relay import relay_manager


def get_user_id_for_tool(token_param: Optional[str] = None) -> str:
    """
    Resolve which user is requesting the action:
    1. From explicit 'token' argument passed to the tool
    2. From HTTP Authorization Bearer header
    3. From HTTP URL query parameter (?token=...)
    """
    # 1. Explicit argument
    if token_param:
        user_id = verify_token(token_param)
        if user_id:
            return user_id

    # 2. Extract from FastMCP HTTP request context
    try:
        from fastmcp.server.dependencies import get_http_request
        req = get_http_request()
        if req is not None:
            # Check Bearer header
            auth = req.headers.get("Authorization", "")
            if auth.startswith("Bearer "):
                tok = auth[7:].strip()
                user_id = verify_token(tok)
                if user_id:
                    return user_id

            # Check query parameters
            query_token = req.query_params.get("token") or req.query_params.get("api_key")
            if query_token:
                user_id = verify_token(query_token.strip())
                if user_id:
                    return user_id
    except Exception:
        pass

    raise PermissionError(
        "Authentication required: No valid token provided. "
        "Supply 'Authorization: Bearer <token>', query param '?token=<token>', "
        "or include 'token' in the tool parameters."
    )


def register_tools(mcp: FastMCP):
    """Register all workspace and IDE tools on the FastMCP instance."""

    @mcp.tool(
        name="read_workspace_file",
        description="Read lines from a file in the user's local IDE workspace."
    )
    async def read_workspace_file(
        path: str,
        max_lines: int = 500,
        start_line: int = 1,
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        user_id = get_user_id_for_tool(token)
        return await relay_manager.dispatch_task(
            user_id=user_id,
            tool_name="read_workspace_file",
            parameters={"path": path, "max_lines": max_lines, "start_line": start_line}
        )

    @mcp.tool(
        name="write_workspace_file",
        description="Create or overwrite a file in the user's local IDE workspace."
    )
    async def write_workspace_file(
        path: str,
        content: str,
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        user_id = get_user_id_for_tool(token)
        return await relay_manager.dispatch_task(
            user_id=user_id,
            tool_name="write_workspace_file",
            parameters={"path": path, "content": content}
        )

    @mcp.tool(
        name="edit_workspace_file",
        description="Replace a target substring with replacement text in a file."
    )
    async def edit_workspace_file(
        path: str,
        old_str: str,
        new_str: str,
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        user_id = get_user_id_for_tool(token)
        return await relay_manager.dispatch_task(
            user_id=user_id,
            tool_name="edit_workspace_file",
            parameters={"path": path, "old_str": old_str, "new_str": new_str}
        )

    @mcp.tool(
        name="list_workspace_directory",
        description="List files and directories in the user's local IDE workspace."
    )
    async def list_workspace_directory(
        path: str = ".",
        max_depth: int = 2,
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        user_id = get_user_id_for_tool(token)
        return await relay_manager.dispatch_task(
            user_id=user_id,
            tool_name="list_workspace_directory",
            parameters={"path": path, "max_depth": max_depth}
        )

    @mcp.tool(
        name="search_workspace_files",
        description="Search for text across files within the user's local workspace."
    )
    async def search_workspace_files(
        query: str,
        path: str = ".",
        file_pattern: str = "*",
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        user_id = get_user_id_for_tool(token)
        return await relay_manager.dispatch_task(
            user_id=user_id,
            tool_name="search_workspace_files",
            parameters={"query": query, "path": path, "file_pattern": file_pattern}
        )

    @mcp.tool(
        name="run_terminal_command",
        description="Execute a shell command inside the user's local workspace directory."
    )
    async def run_terminal_command(
        command: str,
        timeout_seconds: int = 30,
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        user_id = get_user_id_for_tool(token)
        return await relay_manager.dispatch_task(
            user_id=user_id,
            tool_name="run_terminal_command",
            parameters={"command": command, "timeout_seconds": timeout_seconds}
        )

    @mcp.tool(
        name="get_workspace_context",
        description="Get overview of the local workspace, git branch, and status."
    )
    async def get_workspace_context(
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        user_id = get_user_id_for_tool(token)
        return await relay_manager.dispatch_task(
            user_id=user_id,
            tool_name="get_workspace_context",
            parameters={}
        )
