import asyncio
import tempfile
import pytest
from server.app import mcp_server
from server.auth import register_token
from client.executor import LocalIDEExecutor
from server.relay import relay_manager


@pytest.mark.asyncio
async def test_fastmcp_tool_invocation():
    token = "fastmcp_test_token"
    user_id = "test_developer"
    register_token(token, user_id)

    with tempfile.TemporaryDirectory() as temp_dir:
        executor = LocalIDEExecutor(workspace_dir=temp_dir)
        executor.write_file("main.py", "print('Hello from Antigravity IDE!')\n")

        # Mark user as online in relay
        relay_manager.update_heartbeat(user_id)

        # Mock the local bridge polling loop in background
        async def mock_local_bridge():
            task = await relay_manager.poll_task(user_id=user_id, wait_timeout=3.0)
            if task:
                assert task["tool_name"] == "read_workspace_file"
                res = executor.read_file(task["parameters"]["path"])
                await relay_manager.submit_result(task["task_id"], result=res)

        bridge_task = asyncio.create_task(mock_local_bridge())

        # Call the tool through FastMCP with explicit token
        tool_result = await mcp_server.call_tool(
            "read_workspace_file",
            {"path": "main.py", "token": token}
        )

        await bridge_task

        assert tool_result is not None
        # FastMCP call_tool returns CallToolResult with content
        content_text = ""
        for block in tool_result.content:
            if hasattr(block, "text"):
                content_text += block.text
            elif isinstance(block, dict) and "text" in block:
                content_text += block["text"]
            else:
                content_text += str(block)

        assert "Hello from Antigravity IDE!" in content_text


@pytest.mark.asyncio
async def test_fastmcp_new_file_tools():
    token = "fastmcp_test_token_2"
    user_id = "test_developer_2"
    register_token(token, user_id)

    with tempfile.TemporaryDirectory() as temp_dir:
        executor = LocalIDEExecutor(workspace_dir=temp_dir)
        executor.write_file("data.json", '{"key": "value"}')

        relay_manager.update_heartbeat(user_id)

        async def mock_local_bridge():
            task = await relay_manager.poll_task(user_id=user_id, wait_timeout=3.0)
            if task:
                assert task["tool_name"] == "get_file_info"
                res = executor.get_file_info(task["parameters"]["path"])
                await relay_manager.submit_result(task["task_id"], result=res)

        bridge_task = asyncio.create_task(mock_local_bridge())

        tool_result = await mcp_server.call_tool(
            "get_file_info",
            {"path": "data.json", "token": token}
        )

        await bridge_task

        assert tool_result is not None
        content_text = ""
        for block in tool_result.content:
            if hasattr(block, "text"):
                content_text += block.text
            elif isinstance(block, dict) and "text" in block:
                content_text += block["text"]
            else:
                content_text += str(block)

        assert "data.json" in content_text
        assert "file" in content_text


@pytest.mark.asyncio
async def test_streamable_http_gemini_handshake():
    from server.app import app
    from starlette.testclient import TestClient

    with TestClient(app) as client:
        # 1. Probe check (GET /mcp)
        r_get = client.get("/mcp")
        assert r_get.status_code == 200
        assert "model-context-protocol" in r_get.text

        # 2. Initialize handshake (POST /mcp)
        r_init = client.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "gemini-web", "version": "1.0"}
            }
        })
        assert r_init.status_code == 200
        assert "serverInfo" in r_init.text

        # 3. List tools (POST /mcp)
        r_tools = client.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        })
        assert r_tools.status_code == 200
        assert "list_projects" in r_tools.text

        # 4. Fallback test: verify get_user_id_for_tool routes to active bridge without token
        from server.tools import get_user_id_for_tool
        from server.relay import relay_manager
        relay_manager.update_heartbeat("test_gemini_active_user")
        assert get_user_id_for_tool(None) == "test_gemini_active_user"


