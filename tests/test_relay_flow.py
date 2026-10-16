import asyncio
import tempfile
import pytest
from httpx import AsyncClient, ASGITransport
from server.app import app
from server.auth import register_token
from client.executor import LocalIDEExecutor
from server.relay import relay_manager


@pytest.mark.asyncio
async def test_full_relay_and_auth_flow():
    token = "test_secret_token_123"
    user_id = "test_user_alice"
    register_token(token, user_id)

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a sample file in the user's workspace
        executor = LocalIDEExecutor(workspace_dir=temp_dir)
        executor.write_file("sample.py", "def add(a, b):\n    return a + b\n")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token}"}

            # 1. Unauthenticated request should fail
            unauth_res = await client.get("/api/status")
            assert unauth_res.status_code == 401

            # 2. Authenticated status check before client is online
            status_res = await client.get("/api/status", headers=headers)
            assert status_res.status_code == 200
            assert status_res.json()["local_bridge_connected"] is False

            # 3. Simulate local client heartbeat / polling
            poll_task = asyncio.create_task(
                client.post("/api/relay/poll", headers=headers, json={"wait_timeout": 5.0})
            )

            # Wait briefly for poll request to register heartbeat
            await asyncio.sleep(0.1)

            # Check status now: client should be reported online
            online_res = await client.get("/api/status", headers=headers)
            assert online_res.json()["local_bridge_connected"] is True

            # 4. Dispatch a tool call asynchronously (e.g. from ChatGPT / Claude)
            async def run_tool_call():
                return await client.post(
                    "/api/tools/read_workspace_file",
                    headers=headers,
                    json={"path": "sample.py"}
                )

            tool_task = asyncio.create_task(run_tool_call())

            # 5. Local client receives task from the poll endpoint
            poll_res = await poll_task
            assert poll_res.status_code == 200
            data = poll_res.json()
            assert data["task"] is not None
            task = data["task"]
            assert task["tool_name"] == "read_workspace_file"
            assert task["parameters"]["path"] == "sample.py"

            # 6. Local client executes the tool locally
            local_result = executor.read_file(
                path=task["parameters"]["path"],
                max_lines=task["parameters"].get("max_lines", 500),
                start_line=task["parameters"].get("start_line", 1)
            )

            # 7. Local client submits result back to relay
            submit_res = await client.post(
                "/api/relay/result",
                headers=headers,
                json={
                    "task_id": task["task_id"],
                    "result": local_result,
                    "error": None
                }
            )
            assert submit_res.status_code == 200

            # 8. Web AI tool request completes with returned data
            tool_res = await tool_task
            assert tool_res.status_code == 200
            body = tool_res.json()
            assert body["status"] == "success"
            assert "def add(a, b):" in body["result"]["content"]
