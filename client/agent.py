import argparse
import asyncio
import os
import sys
import httpx
from typing import Dict, Any, Optional
from dotenv import load_dotenv

from client.executor import LocalIDEExecutor

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()


class LocalBridgeAgent:
    """
    Connects local IDE / workspace to the cloud MCP server via outbound polling.
    No port forwarding or public IP required.
    """
    def __init__(self, server_url: str, auth_token: str, workspace_dir: str = "."):
        self.server_url = server_url.rstrip("/")
        self.auth_token = auth_token
        self.workspace_dir = workspace_dir
        self.executor = LocalIDEExecutor(workspace_dir=workspace_dir)
        self.headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "User-Agent": "Antigravity-Local-Bridge/1.0",
            "Content-Type": "application/json"
        }
        self.running = False

    async def execute_task(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        """Route incoming tool request to the appropriate executor method."""
        params = parameters or {}

        if tool_name in ("read_workspace_file", "read_file"):
            return self.executor.read_file(
                path=params.get("path", ""),
                max_lines=params.get("max_lines", 500),
                start_line=params.get("start_line", 1)
            )
        elif tool_name in ("write_workspace_file", "write_file"):
            return self.executor.write_file(
                path=params.get("path", ""),
                content=params.get("content", "")
            )
        elif tool_name in ("edit_workspace_file", "edit_file"):
            return self.executor.edit_file(
                path=params.get("path", ""),
                old_str=params.get("old_str", ""),
                new_str=params.get("new_str", "")
            )
        elif tool_name in ("list_workspace_directory", "list_directory"):
            return self.executor.list_directory(
                path=params.get("path", "."),
                max_depth=params.get("max_depth", 2)
            )
        elif tool_name in ("search_workspace_files", "search_files"):
            return self.executor.search_files(
                query=params.get("query", ""),
                path=params.get("path", "."),
                file_pattern=params.get("file_pattern", "*")
            )
        elif tool_name in ("run_terminal_command", "execute_command"):
            return self.executor.execute_command(
                command=params.get("command", ""),
                timeout_seconds=params.get("timeout_seconds", 30)
            )
        elif tool_name in ("get_workspace_context", "get_context"):
            return self.executor.get_context()
        else:
            raise NotImplementedError(f"Tool '{tool_name}' is not recognized by the local bridge.")

    async def run(self):
        """Main event loop: poll for jobs, execute, and return results."""
        self.running = True
        print(f"\n=======================================================")
        print(f"🚀 Antigravity IDE Local Bridge Started")
        print(f"📁 Workspace:  {self.executor.workspace_path}")
        print(f"🌐 Cloud Relay: {self.server_url}")
        print(f"🔑 Auth Token: {self.auth_token[:8]}...{self.auth_token[-4:] if len(self.auth_token) > 12 else ''}")
        print(f"=======================================================\n")
        print("Connected to cloud relay. Waiting for AI commands (ChatGPT, Gemini, etc.)...\n")

        poll_url = f"{self.server_url}/api/relay/poll"
        result_url = f"{self.server_url}/api/relay/result"

        async with httpx.AsyncClient(timeout=30.0) as client:
            consecutive_errors = 0

            while self.running:
                try:
                    # Poll cloud server for pending tasks (long polling)
                    response = await client.post(poll_url, headers=self.headers, json={"wait_timeout": 15})
                    
                    if response.status_code == 401:
                        print(f"❌ Authentication failed: Invalid token '{self.auth_token}'. Exiting.")
                        self.running = False
                        break

                    if response.status_code != 200:
                        print(f"⚠️ Relay error ({response.status_code}): {response.text}")
                        await asyncio.sleep(3)
                        continue

                    data = response.json()
                    consecutive_errors = 0
                    task = data.get("task")

                    if not task:
                        # Normal timeout on long-poll, loop and poll again
                        continue

                    task_id = task.get("task_id")
                    tool_name = task.get("tool_name")
                    params = task.get("parameters", {})

                    print(f"⚡ [AI REQUEST] Tool: {tool_name} | Params: {params}")

                    result = None
                    error = None
                    try:
                        result = await self.execute_task(tool_name, params)
                        print(f"✅ [SUCCESS] Finished {tool_name}")
                    except Exception as e:
                        error = str(e)
                        print(f"❌ [TOOL ERROR] {error}")

                    # Submit result back to cloud relay
                    await client.post(
                        result_url,
                        headers=self.headers,
                        json={
                            "task_id": task_id,
                            "result": result,
                            "error": error
                        }
                    )

                except (httpx.ConnectError, httpx.TimeoutException) as e:
                    consecutive_errors += 1
                    wait_time = min(10, 2 ** consecutive_errors)
                    print(f"🔄 Connection to cloud relay interrupted. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                except asyncio.CancelledError:
                    print("\n🛑 Local bridge stopping...")
                    self.running = False
                    break
                except Exception as e:
                    print(f"⚠️ Unexpected error: {str(e)}")
                    await asyncio.sleep(2)


def main():
    parser = argparse.ArgumentParser(description="Antigravity IDE Local Bridge Client")
    parser.add_argument("--server", default=os.getenv("MCP_SERVER_URL", "http://localhost:8000"), help="Cloud MCP Server URL")
    parser.add_argument("--key", default=os.getenv("MCP_AUTH_TOKEN", ""), help="User Auth Token")
    parser.add_argument("--dir", default=os.getenv("MCP_WORKSPACE_DIR", "."), help="Path to local workspace directory")

    args = parser.parse_args()

    if not args.key:
        print("❌ Error: Authentication token is required.")
        print("Specify --key <your-token> or set MCP_AUTH_TOKEN in environment / .env file.")
        sys.exit(1)

    agent = LocalBridgeAgent(server_url=args.server, auth_token=args.key, workspace_dir=args.dir)
    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        print("\n👋 Disconnected.")


if __name__ == "__main__":
    main()
