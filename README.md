# Antigravity Multi-Tenant IDE MCP Bridge 🚀

> Connect Web-based AI assistants (**ChatGPT, Gemini Web, Claude, Antigravity**) directly and securely to local IDEs (**VS Code, Antigravity IDE**) with multi-user authentication, ready to deploy to **Vercel**.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-Protocol-purple.svg)](https://modelcontextprotocol.io)
[![FastMCP](https://img.shields.io/badge/FastMCP-v4.1.0-green.svg)](https://github.com/jlowin/fastmcp)
[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new)

---

## 💡 Overview

Web-based AI interfaces (like ChatGPT web with Custom GPTs/MCP, or Gemini Web) run in the cloud and cannot directly reach into your local machine through firewalls and NAT routers.

**Antigravity Multi-Tenant IDE MCP Bridge** solves this with a secure cloud relay architecture:
1. **Cloud Gateway (FastMCP / FastAPI)**: Hosted on Vercel or any cloud provider. Provides MCP SSE (`/mcp/sse`) and REST endpoints.
2. **Local Bridge Companion (`client.agent`)**: A lightweight Python CLI running locally on the user's machine in their IDE workspace. Dials *out* to the cloud relay. No port forwarding or public IP required.
3. **Multi-Tenant Token Isolation**: Each user gets a private token. When User A speaks to Gemini or ChatGPT, commands and file operations execute **exclusively** on User A's workspace.

---

## 🏗️ Architecture

```
┌─────────────────────────────────┐
│ Web AI (ChatGPT / Gemini Web)   │
└────────────────┬────────────────┘
                 │ 1. Tool Call + Bearer Token
                 ▼
┌────────────────────────────────────────────────────────┐
│ Cloud MCP Gateway (Vercel Serverless / FastMCP)        │
│ - Validates user token & isolates session              │
│ - Enqueues tool action for User's IDE                  │
└────────────────┬───────────────────────────────────────┘
                 │ 2. Long-polling / Relay Channel
                 │    (Outbound from user's PC)
┌────────────────┴───────────────────────────────────────┐
│ Local IDE Bridge (VS Code / Antigravity Workspace)    │
│ - Sandboxed Workspace File Ops                         │
│ - Terminal Execution                                   │
│ - Workspace Search & Git Context                       │
└────────────────────────────────────────────────────────┘
```

---

## ✨ Features

- **Multi-Tenant Isolation**: Supports multiple users on a single hosted deployment. User requests are routed only to their specific paired machine.
- **Vercel Serverless Ready**: Uses an ASGI adapter (`mangum` / native ASGI) compatible with Vercel serverless functions.
- **Zero Inbound Ports**: Local machines connect outbound to the cloud relay. Works behind any firewall, VPN, or home NAT.
- **Workspace Sandboxing**: Path traversal protection prevents AI from accessing directories outside the designated workspace.
- **Dual Support**:
  - **Standard MCP SSE**: Connects to Claude, Gemini, Antigravity, and MCP clients (`/mcp/sse`).
  - **Direct REST API**: Works seamlessly with ChatGPT Custom GPT Actions (`/api/tools/{tool_name}`).

---

## 🛠️ Tools Provided to the AI

| Tool | Description |
|---|---|
| `read_workspace_file` | Read lines or entire contents of a workspace file. |
| `write_workspace_file` | Create or replace a file in the workspace. |
| `edit_workspace_file` | Replace specific code/text snippets within a file. |
| `list_workspace_directory` | Explore directories and inspect file tree structures. |
| `search_workspace_files` | Search for text or symbols across workspace files. |
| `run_terminal_command` | Execute commands (tests, builds, lints) in the workspace. |
| `get_workspace_context` | Query current Git branch, status, and repository state. |

---

## 🚀 Quickstart Guide

### 1. Setup Local Environment

```bash
# Clone the repository
git clone https://github.com/your-username/vscode-antigravity-mcp.git
cd vscode-antigravity-mcp

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Generate user pairing tokens with the helper script:

```bash
python scripts/register_user.py alice
```

Add the generated token to `AUTH_TOKENS` in your `.env` file:
```env
AUTH_TOKENS="your_generated_token:alice"
```

### 3. Run Locally (Dev Mode)

Start the cloud gateway locally:
```bash
python scripts/start_server.py
```
Server runs at `http://localhost:8000`.

In another terminal, start the local bridge inside your project workspace:
```bash
python -m client.agent --key "your_generated_token" --server "http://localhost:8000" --dir "."
```

---

## ☁️ Deploying to Vercel

1. Push your repository to GitHub.
2. Import the repository in [Vercel](https://vercel.com).
3. In Project Settings -> **Environment Variables**, add:
   - `AUTH_TOKENS`: e.g. `your_token:user1,another_token:user2`
   - `ADMIN_SECRET_KEY`: A strong secret for admin token generation.
4. Deploy! Your Vercel domain will be live (e.g. `https://your-mcp.vercel.app`).

---

## 🤖 Connecting to Web AI Assistants

### A. ChatGPT (Custom GPTs / Actions)
1. Go to **ChatGPT** -> **Explore GPTs** -> **Create a GPT**.
2. Under **Actions**, click **Create new action**.
3. Import the OpenAPI schema from `https://your-mcp.vercel.app/openapi.json`.
4. Under **Authentication**, select **Bearer** and paste your user token.

### B. Gemini Web / Claude / Antigravity (MCP SSE)
Configure your MCP client with:
- **Server Type**: SSE
- **URL**: `https://your-mcp.vercel.app/mcp/sse?token=YOUR_USER_TOKEN`
- **Headers**:
  ```json
  {
    "Authorization": "Bearer YOUR_USER_TOKEN"
  }
  ```

---

## 🧪 Running Tests

The test suite validates security sandboxing, local executor operations, and the full asynchronous relay cycle:

```bash
pytest -v tests
```

---

## 🔒 Security & Sandboxing

- **Path Boundaries**: File operations resolve paths relative to the designated workspace directory. Attempts to escape via `../` raise `PermissionError`.
- **Token Protection**: All relay polling and tool invocations require a valid pre-shared or generated token.
- **Non-Destructive Defaults**: Commands run within execution timeouts to prevent hung processes.

---

## 📄 License

MIT License. Open-source for personal and commercial use.
