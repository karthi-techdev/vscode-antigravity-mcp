# Antigravity Multi-Tenant IDE MCP Bridge 🚀

> Connect Web AI assistants (**Gemini Web, ChatGPT, Claude**) directly and securely to your local IDE (**VS Code, Antigravity IDE**) — with multi-user isolation, zero open ports, and hosted on **Vercel**.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-Protocol-purple.svg)](https://modelcontextprotocol.io)
[![FastMCP](https://img.shields.io/badge/FastMCP-v4.1.0-green.svg)](https://github.com/jlowin/fastmcp)
[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/karthi-techdev/vscode-antigravity-mcp)

---

## 💡 How It Works

Cloud AI models (Gemini Web, ChatGPT) cannot directly reach into your computer because of firewalls and Wi-Fi routers (NAT). 

**Antigravity MCP Bridge** creates a secure outbound tunnel between your local project and the cloud:

```
┌──────────────────────────────────────┐
│       Web AI Assistant               │
│   (Gemini Web / ChatGPT / Claude)    │
└──────────────────┬───────────────────┘
                   │ 1. Tool Call + Your Token
                   ▼
┌────────────────────────────────────────────────────────┐
│ Cloud MCP Gateway (Hosted on Vercel)                   │
│ - Authenticates your private token                     │
│ - Routes tasks exclusively to your computer            │
└──────────────────▲─────────────────────────────────────┘
                   │ 2. Outbound polling (Zero inbound ports!)
                   │    Works behind any Wi-Fi or firewall
┌──────────────────┴─────────────────────────────────────┐
│ Your Local Computer (Any Project Workspace)            │
│ - Reads/edits files in your project                    │
│ - Runs builds, tests, or lints in terminal             │
│ - Sandboxed strictly to your chosen folder             │
└────────────────────────────────────────────────────────┘
```

---

## 🚀 Quickstart for End-Users (ZERO Git Cloning Required)

If you are a developer who just wants to connect your local project to Gemini Web or ChatGPT using an existing hosted bridge, **you do NOT need to clone this repository!**

### Step 1: Download the Bridge into your project

Open your terminal in **whatever project you want the AI to work on** (e.g. `C:\my-cool-app`), and run:

#### Windows (PowerShell):
```powershell
curl.exe -o bridge.py https://vscode-antigravity-mcp.vercel.app/bridge.py
```

#### macOS / Linux:
```bash
curl -o bridge.py https://vscode-antigravity-mcp.vercel.app/bridge.py
```

---

### Step 2: Start the Bridge

Run `bridge.py` with your personal token and the server URL:

```bash
python bridge.py --key "YOUR_USER_TOKEN" --server "https://vscode-antigravity-mcp.vercel.app"
```

You will see:
```text
============================================================
🚀 Antigravity IDE Bridge Connected
📁 Workspace:   /path/to/your/project
🌐 Cloud Relay: https://vscode-antigravity-mcp.vercel.app
============================================================
Waiting for AI commands from Gemini / ChatGPT in browser...
```
*(Leave this terminal tab open in the background while you chat with your AI).*

---

### Step 3: Connect to Gemini Web or ChatGPT

#### In Gemini Web:
1. Open [Gemini](https://gemini.google.com/) -> **Settings** -> **Connected Apps** -> **Connect to an MCP server**.
2. **MCP server URL**:
   ```text
   https://vscode-antigravity-mcp.vercel.app/mcp/sse?token=YOUR_USER_TOKEN
   ```
3. Leave **Client ID** and **Client secret** blank.
4. Click **Next**!

#### In ChatGPT (Custom GPT Actions):
1. In your Custom GPT -> **Actions** -> **Import from URL**:
   ```text
   https://vscode-antigravity-mcp.vercel.app/openapi.json
   ```
2. Set Authentication to **Bearer** and paste `YOUR_USER_TOKEN`.

---

## 🛠️ Tools Given to the AI

Once connected, your AI assistant can invoke these tools in real-time on your computer:

| Tool | What It Does |
|---|---|
| `read_workspace_file(path)` | Reads lines or full contents of any file in your project. |
| `write_workspace_file(path, content)` | Creates or replaces files in your workspace. |
| `edit_workspace_file(path, old, new)` | Finds and replaces specific code blocks in a file. |
| `list_workspace_directory(path)` | Explores directories and inspects the file tree. |
| `search_workspace_files(query)` | Searches for text, classes, or symbols across your codebase. |
| `run_terminal_command(command)` | Runs commands (tests, builds, lints) in your project. |
| `get_workspace_context()` | Queries Git branch, status, and modified files. |

---

## ☁️ For Admins: Self-Hosting on Vercel

If you want to host your own private or company-wide MCP Gateway:

### 1. Click Deploy
Click the button below to fork and deploy directly to Vercel for free:

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/karthi-techdev/vscode-antigravity-mcp)

### 2. Configure Environment Variables in Vercel
During setup (or in Vercel **Settings ➔ Environment Variables**), add:

| Variable | Description | Example |
|---|---|---|
| `AUTH_TOKENS` | Comma-separated list of `token:user_id` pairs | `secret_alice:alice,secret_bob:bob` |
| `ADMIN_SECRET_KEY` | Secret password for admin API endpoints | `my_super_secret_admin_password` |

### 3. Generate New User Tokens Anytime
You can generate tokens anytime locally with the helper script:
```powershell
python scripts/register_user.py <username>
```

---

## 🔒 Security & Privacy

* **Sandbox Scoping**: The bridge enforces strict directory boundaries. Any attempt by the AI to access files outside your chosen project directory (`../../etc/passwd` or `C:\Windows`) is blocked with a `PermissionError`.
* **Zero Inbound Ports**: Your computer never opens an open port to the public internet. It only dials outward via HTTPS long-polling.
* **Multi-Tenant Isolation**: Tool requests are routed strictly based on the token. User A's AI cannot see or execute actions on User B's machine.

---

## ❓ Frequently Asked Questions (FAQ)

### 1. Do other developers need to clone this repository?
**No.** Other developers only need the single [`bridge.py`](https://vscode-antigravity-mcp.vercel.app/bridge.py) file. They run it inside their own project folder and connect immediately.

### 2. What if I switch to another project on my computer?
Simply run `bridge.py` inside that other project's folder:
```powershell
python bridge.py --key "YOUR_KEY" --server "https://your-server.vercel.app" --dir "."
```

### 3. Can I run commands in the terminal?
Yes, tools like `run_terminal_command` execute commands directly in your workspace with configurable timeouts to prevent hanging.

---

## 📄 License

MIT License. Open-source and free for both personal and commercial use.
