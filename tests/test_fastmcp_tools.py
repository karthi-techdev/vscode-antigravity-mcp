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
