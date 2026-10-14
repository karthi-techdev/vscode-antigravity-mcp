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

    # 3. Fallback: If token was not attached to URL/header (e.g. Gemini Connected Apps added without ?token=),
    # automatically route to the user's active local bridge!
    import time
    now = time.time()
    active_users = [uid for uid, t in relay_manager.client_heartbeats.items() if (now - t) < 60.0]
    if active_users:
        return max(active_users, key=lambda u: relay_manager.client_heartbeats.get(u, 0))

    if relay_manager.client_heartbeats:
        return max(relay_manager.client_heartbeats.items(), key=lambda x: x[1])[0]

    from server.auth import DYNAMIC_TOKENS
    if DYNAMIC_TOKENS:
        return list(DYNAMIC_TOKENS.values())[-1]

    raise PermissionError(
        "No active local IDE bridge detected. Please start your local companion: "
        "`python bridge.py --key <your-key>`"
    )


def register_tools(mcp: FastMCP):
    """Register all workspace and IDE tools on the FastMCP instance."""

    # -------------------------------------------------------------------------
    # System-Wide Multi-Project Management Tools
    # -------------------------------------------------------------------------

    @mcp.tool(
        name="list_projects",
        description="Discover and list all project folders and repositories available on the user's system."
    )
    async def list_projects(
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        user_id = get_user_id_for_tool(token)
        return await relay_manager.dispatch_task(
            user_id=user_id,
            tool_name="list_projects",
            parameters={}
        )

    @mcp.tool(
        name="set_active_project",
        description="Switch the active project context to a specific project folder on the user's machine."
    )
    async def set_active_project(
        project_name: str,
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        user_id = get_user_id_for_tool(token)
        return await relay_manager.dispatch_task(
            user_id=user_id,
            tool_name="set_active_project",
            parameters={"project_name": project_name}
        )

    @mcp.tool(
        name="get_active_project",
        description="Get the currently active project name, workspace path, and git status on the user's machine."
    )
    async def get_active_project(
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        user_id = get_user_id_for_tool(token)
        return await relay_manager.dispatch_task(
            user_id=user_id,
            tool_name="get_active_project",
            parameters={}
        )

    # -------------------------------------------------------------------------
    # Workspace Code & File Operations
    # -------------------------------------------------------------------------

    @mcp.tool(
        name="read_workspace_file",
        description="Read lines from a file in the user's workspace or specified project."
    )
    async def read_workspace_file(
        path: str,
        max_lines: int = 500,
        start_line: int = 1,
        project: Optional[str] = None,
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        user_id = get_user_id_for_tool(token)
        return await relay_manager.dispatch_task(
            user_id=user_id,
            tool_name="read_workspace_file",
            parameters={"path": path, "max_lines": max_lines, "start_line": start_line, "project": project}
        )

    @mcp.tool(
        name="write_workspace_file",
        description="Create or overwrite a file in the user's workspace or specified project."
    )
    async def write_workspace_file(
        path: str,
        content: str,
        project: Optional[str] = None,
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        user_id = get_user_id_for_tool(token)
        return await relay_manager.dispatch_task(
            user_id=user_id,
            tool_name="write_workspace_file",
            parameters={"path": path, "content": content, "project": project}
        )

    @mcp.tool(
        name="edit_workspace_file",
        description="Replace a target substring with replacement text in a workspace file."
    )
    async def edit_workspace_file(
        path: str,
        old_str: str,
        new_str: str,
        project: Optional[str] = None,
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        user_id = get_user_id_for_tool(token)
        return await relay_manager.dispatch_task(
            user_id=user_id,
            tool_name="edit_workspace_file",
            parameters={"path": path, "old_str": old_str, "new_str": new_str, "project": project}
        )

    @mcp.tool(
        name="create_directory",
        description="Create a new directory (and any necessary parent directories) in the workspace or specified project."
    )
    async def create_directory(
        path: str,
        project: Optional[str] = None,
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        user_id = get_user_id_for_tool(token)
        return await relay_manager.dispatch_task(
            user_id=user_id,
            tool_name="create_directory",
            parameters={"path": path, "project": project}
        )

    @mcp.tool(
        name="delete_file",
        description="Delete a file or directory inside the workspace or specified project. Set recursive=True to delete a non-empty directory."
    )
    async def delete_file(
        path: str,
        recursive: bool = False,
        project: Optional[str] = None,
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        user_id = get_user_id_for_tool(token)
        return await relay_manager.dispatch_task(
            user_id=user_id,
            tool_name="delete_file",
            parameters={"path": path, "recursive": recursive, "project": project}
        )

    @mcp.tool(
        name="move_or_rename_file",
        description="Move or rename a file or directory within the workspace or specified project."
    )
    async def move_or_rename_file(
        source_path: str,
        destination_path: str,
        overwrite: bool = False,
        project: Optional[str] = None,
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        user_id = get_user_id_for_tool(token)
        return await relay_manager.dispatch_task(
            user_id=user_id,
            tool_name="move_or_rename_file",
            parameters={
                "source_path": source_path,
                "destination_path": destination_path,
                "overwrite": overwrite,
                "project": project
            }
        )

    @mcp.tool(
        name="get_file_info",
        description="Get detailed metadata, size, timestamps, and line count for a file or directory."
    )
    async def get_file_info(
        path: str,
        project: Optional[str] = None,
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        user_id = get_user_id_for_tool(token)
        return await relay_manager.dispatch_task(
            user_id=user_id,
            tool_name="get_file_info",
            parameters={"path": path, "project": project}
        )

    @mcp.tool(
        name="list_workspace_directory",
        description="List files and directories in the user's workspace or specified project."
    )
    async def list_workspace_directory(
        path: str = ".",
        max_depth: int = 2,
        project: Optional[str] = None,
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        user_id = get_user_id_for_tool(token)
        return await relay_manager.dispatch_task(
            user_id=user_id,
            tool_name="list_workspace_directory",
            parameters={"path": path, "max_depth": max_depth, "project": project}
        )

    @mcp.tool(
        name="search_workspace_files",
        description="Search for text across files within the workspace or specified project."
    )
    async def search_workspace_files(
        query: str,
        path: str = ".",
        file_pattern: str = "*",
        project: Optional[str] = None,
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        user_id = get_user_id_for_tool(token)
        return await relay_manager.dispatch_task(
            user_id=user_id,
            tool_name="search_workspace_files",
            parameters={"query": query, "path": path, "file_pattern": file_pattern, "project": project}
        )

    @mcp.tool(
        name="run_terminal_command",
        description="Execute a general shell command inside the active project directory."
    )
    async def run_terminal_command(
        command: str,
        timeout_seconds: int = 30,
        project: Optional[str] = None,
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        user_id = get_user_id_for_tool(token)
        return await relay_manager.dispatch_task(
            user_id=user_id,
            tool_name="run_terminal_command",
            parameters={"command": command, "timeout_seconds": timeout_seconds, "project": project}
        )

    @mcp.tool(
        name="run_powershell_command",
        description="Execute a PowerShell command or script in the active project workspace with full PowerShell environment and UTF-8 support."
    )
    async def run_powershell_command(
        command: str,
        timeout_seconds: int = 60,
        project: Optional[str] = None,
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        user_id = get_user_id_for_tool(token)
        return await relay_manager.dispatch_task(
            user_id=user_id,
            tool_name="run_powershell_command",
            parameters={"command": command, "timeout_seconds": timeout_seconds, "project": project}
        )

    @mcp.tool(
        name="run_cmd_command",
        description="Execute a Command Prompt (cmd.exe) command or batch command in the active project workspace."
    )
    async def run_cmd_command(
        command: str,
        timeout_seconds: int = 60,
        project: Optional[str] = None,
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        user_id = get_user_id_for_tool(token)
        return await relay_manager.dispatch_task(
            user_id=user_id,
            tool_name="run_cmd_command",
            parameters={"command": command, "timeout_seconds": timeout_seconds, "project": project}
        )

    @mcp.tool(
        name="run_git_command",
        description="Execute a Git command (e.g. 'status --short', 'diff', 'log -n 5', 'branch -a', 'commit -m \"...\"', 'add .') in the project repository."
    )
    async def run_git_command(
        subcommand: str,
        timeout_seconds: int = 60,
        project: Optional[str] = None,
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        user_id = get_user_id_for_tool(token)
        return await relay_manager.dispatch_task(
            user_id=user_id,
            tool_name="run_git_command",
            parameters={"subcommand": subcommand, "timeout_seconds": timeout_seconds, "project": project}
        )

    @mcp.tool(
        name="get_workspace_context",
        description="Get overview of the active project, git branch, and status."
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
