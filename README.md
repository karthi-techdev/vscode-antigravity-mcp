# Universal Local IDE & Workspace MCP Bridge 🚀

> Connect Web AI assistants (**ChatGPT, Claude Web, Gemini Web**) directly and securely to **ANY local IDE or developer workspace** (**VS Code, Cursor, Windsurf, JetBrains / IntelliJ / PyCharm, Antigravity, Zed, Neovim, Terminal**) — with multi-user isolation, zero open ports, and live interactive terminal logs.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-Protocol-purple.svg)](https://modelcontextprotocol.io)
[![FastMCP](https://img.shields.io/badge/FastMCP-v4.1.0-green.svg)](https://github.com/jlowin/fastmcp)
[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/karthi-techdev/vscode-antigravity-mcp)

---

## 💡 How It Works

Cloud AI models (ChatGPT, Claude Web, Gemini Web) cannot reach into your computer because of firewalls and Wi-Fi NAT. 

**Universal IDE MCP Bridge** creates an on-demand, outbound connection between your local computer and your hosted MCP Gateway:

```
┌──────────────────────────────────────┐
│       Web AI Assistant               │
│   (ChatGPT / Claude / Gemini)        │
└──────────────────┬───────────────────┘
                   │ 1. Tool Call + Your Token
                   ▼
┌────────────────────────────────────────────────────────┐
│ Cloud MCP Gateway (Hosted on Vercel)                   │
│ - Authenticates your private token                     │
│ - Routes tasks exclusively to your computer            │
│ - Supports Upstash Redis for distributed persistence   │
└──────────────────▲─────────────────────────────────────┘
                   │ 2. Outbound polling (Zero inbound ports!)
                   │    Works behind any Wi-Fi or router
┌──────────────────┴─────────────────────────────────────┐
│ Your Local Computer (On-Demand Bridge Session)         │
│ - Run whenever you want, just like `npm run dev`       │
│ - Live real-time debug logs for every tool & action    │
│ - Reads & edits files, runs terminal/git commands      │
│ - Sandboxed strictly to your chosen projects folder    │
└────────────────────────────────────────────────────────┘
```

---

## 🌐 Web AI Connection Details

Connect any Web AI Chat in your browser to your local computer:

| Platform | Endpoint URL | Format / Protocol |
|---|---|---|
| **Claude Web** *(Custom Connectors)* | `https://vscode-antigravity-mcp.vercel.app/mcp?token=YOUR_SECRET_KEY` | **StreamableHTTP** (Official Claude Connector standard) |
| **Google Gemini Web** *(Connected Apps)* | `https://vscode-antigravity-mcp.vercel.app/mcp?token=YOUR_SECRET_KEY` | **StreamableHTTP** (Official Gemini MCP format) |
| **ChatGPT Web** *(Custom GPTs / Actions)* | `https://vscode-antigravity-mcp.vercel.app/openapi.json` | **OpenAPI Schema Actions** (Direct REST) |
| **ChatGPT Web** *(MCP Connectors)* | `https://vscode-antigravity-mcp.vercel.app/mcp?token=YOUR_SECRET_KEY` | **StreamableHTTP** |
| **Google AI Studio Web** | `https://vscode-antigravity-mcp.vercel.app/openapi.json` | **OpenAPI Function Calling** |
| **Authentication Header** | `Authorization: Bearer YOUR_SECRET_KEY` | Enter your secret key in the connector settings |
| **URL Query Token Option** | `?token=YOUR_SECRET_KEY` | Append token directly in URL |

---

## ⚡ Quick Start: Running the Bridge On-Demand

The bridge is designed as an **interactive, on-demand developer console session** (just like running `npm run dev`). You start it when you need it, observe live real-time debug logs of all AI actions, and stop it anytime with `Ctrl+C`.

### Option 1: Quick Launcher (One-Click)
Double-click [`start_bridge.bat`](file:///c:/projects/vscode-antigravity-mcp/start_bridge.bat) in the project folder.

### Option 2: Run via CLI (Any Terminal)
```bash
python bridge.py
```
*(Or use `bridge` / `ide-bridge` / `mcp-bridge` globally from any folder)*

### Option 3: Specify Your Projects Root & Auth Token
```bash
python bridge.py --root "C:\projects" --key "YOUR_SECRET_KEY"
```

### Option 4: Save Global Defaults
Save your preferred projects directory and token once:
```bash
python bridge.py --save --root "C:\projects" --key "YOUR_SECRET_KEY"
```
Once saved to `~/.universal_ide_bridge.json`, you can simply run `python bridge.py` or `ide-bridge` without any extra flags.

---

## 📊 Live Real-Time Console Logging

When the bridge is running, it streams clear, timestamped diagnostic logs for every operation:

```text
╔════════════════════════════════════════════════════════════════════════════╗
║              🚀 Universal IDE Bridge (On-Demand Dev Session)               ║
╚════════════════════════════════════════════════════════════════════════════╝
📁 Projects Root:    C:\projects
🎯 Active Workspace: C:\projects\vscode-antigravity-mcp
🌐 Cloud Gateway:    https://vscode-antigravity-mcp.vercel.app
🔑 Auth Token:       D4_PROJE...RVER
🟢 Status:           ACTIVE & LISTENING (Press Ctrl+C to stop)
────────────────────────────────────────────────────────────────────────
💡 Ready! When Claude, ChatGPT, or Gemini Web calls a tool, logs will stream below:

[21:30:15] 💚 Gateway heartbeat confirmed (latency: 38ms) | Status: Healthy

──────────────────────────────────────────────────────────────────────
⚡ [21:30:28] INCOMING AI REQUEST: get_active_project
📦 Parameters: {}
📁 Target Project: vscode-antigravity-mcp (C:\projects\vscode-antigravity-mcp)
⚙️ Executing local action...
✅ Local execution completed successfully in 5.8ms
📊 Result: {"projects_root": "C:\\projects", "active_project": "vscode-antigravity-mcp", "git_branch": "main"}
🚀 Delivered result to AI assistant in 12ms (attempt 1)
──────────────────────────────────────────────────────────────────────

🛑 Bridge session stopped by user (Ctrl+C). Clean shutdown complete.
👋 Goodbye!
```

---

## 💻 Connecting Your Web AI Assistant

### 🟣 1. Claude Web (`claude.ai` Custom Connectors)
1. Open **[claude.ai](https://claude.ai)** in your browser.
2. Click your user profile icon (bottom left) ➔ **Settings** ➔ **Connectors** (or **+ Add** ➔ **Custom connector**).
3. Fill in:
   * **Name**: `Universal IDE Bridge`
   * **URL**:
     ```text
     https://vscode-antigravity-mcp.vercel.app/mcp?token=YOUR_SECRET_KEY
     ```
4. Click **Continue**. Claude connects over official **StreamableHTTP** and discovers all 17 tools instantly!

---

### 🟢 2. ChatGPT Web (`chatgpt.com` Custom GPT Actions)
1. In your browser, open **[chatgpt.com](https://chatgpt.com)**.
2. Go to **Explore GPTs** ➔ **+ Create** (top right) ➔ **Configure** tab.
3. Click **Create new action**:
   * **Authentication Type**: `API Key` ➔ `Bearer` ➔ Enter `YOUR_SECRET_KEY`.
   * **Schema**: Click **Import from URL** ➔ Enter:
     ```text
     https://vscode-antigravity-mcp.vercel.app/openapi.json
     ```
   * Click **Import**. ChatGPT imports all tools immediately!
4. Click **Create / Save** ➔ Select **Only me**.
5. Start chatting with your local projects in ChatGPT!

---

### 🔵 3. Google Gemini Web (`gemini.google.com`)
1. Open **[gemini.google.com](https://gemini.google.com)**.
2. Go to **Settings** ➔ **Connected apps** ➔ **Connect to an MCP server**.
3. In **MCP server URL**, enter:
   ```text
   https://vscode-antigravity-mcp.vercel.app/mcp?token=YOUR_SECRET_KEY
   ```
4. Click **Connect**. All workspace tools are now active.

---

## 🛠️ Complete Tools Reference (17 Tools)

### 📂 Multi-Project & Workspace Navigation
| Tool | Description |
|---|---|
| `list_projects()` | Discovers and lists all project folders, detected tech stacks, and Git branches across your system. |
| `set_active_project(project_name)` | Switches the active project context to a different folder on your machine. |
| `get_active_project()` | Inspects current active project name, workspace path, and Git status. |
| `get_workspace_context()` | Queries overview of active workspace, Git branch, and working changes. |

### 📝 File & Directory Operations
| Tool | Description |
|---|---|
| `read_workspace_file(path, [max_lines], [start_line], [project])` | Reads lines or full contents of any file with line numbering. |
| `write_workspace_file(path, content, [project])` | Creates or replaces files in your workspace. |
| `edit_workspace_file(path, old_str, new_str, [project])` | Finds and replaces specific code blocks in a file. |
| `create_directory(path, [project])` | Creates a new directory (and any necessary parent directories). |
| `delete_file(path, [recursive], [project])` | Deletes a file or directory (`recursive=True` for directories). |
| `move_or_rename_file(source_path, destination_path, [overwrite], [project])` | Moves or renames files and directories cleanly. |
| `get_file_info(path, [project])` | Inspects file size, line count, permissions, extension, and timestamps. |
| `list_workspace_directory(path, [max_depth], [project])` | Explores directories and inspects the file tree. |

### 🔍 Code Search
| Tool | Description |
|---|---|
| `search_workspace_files(query, [path], [file_pattern], [project])` | Fast regex/text search for functions, classes, or symbols across your codebase. |

### 💻 Terminals & Version Control
| Tool | Description |
|---|---|
| `run_powershell_command(command, [timeout_seconds], [project])` | Native PowerShell command execution with full UTF-8 encoding support. |
| `run_cmd_command(command, [timeout_seconds], [project])` | Windows Command Prompt (`cmd.exe`) command and batch script execution. |
| `run_git_command(subcommand, [timeout_seconds], [project])` | Direct Git operations (`status`, `diff`, `log`, `branch`, `commit`, `push`, `pull`, etc.). |
| `run_terminal_command(command, [timeout_seconds], [project])` | Default system terminal command execution with configurable timeout. |

---

## ⚙️ CLI Reference (`bridge.py`)

| Flag | Shorthand | Description |
|---|---|---|
| `--root` | `-r` | Path to parent directory containing all projects (e.g. `C:\projects`) |
| `--key` | `-k`, `--token` | User Auth Token (default: reads from config or `.env`) |
| `--server` | `-s` | Cloud MCP Gateway URL (default: `https://vscode-antigravity-mcp.vercel.app`) |
| `--dir` | | Initial workspace directory (default: current directory) |
| `--save` | | Saves the provided `--root`, `--key`, and `--server` as global defaults in `~/.universal_ide_bridge.json` |
| `--show-config` | | Displays current saved global defaults |

---

## ☁️ For Admins: Deploying Your Own Gateway to Vercel

### 1. Click Deploy
[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/karthi-techdev/vscode-antigravity-mcp)

### 2. Environment Variables in Vercel Settings
| Variable | Description | Example |
|---|---|---|
| `AUTH_TOKENS` | Comma-separated list of `token:user_id` pairs | `D4_PROJECT_MCP_SERVER:karthi` |
| `ADMIN_SECRET_KEY` | Secret password for admin API endpoints | `your_admin_secret_key` |
| `UPSTASH_REDIS_REST_URL` *(Optional)* | Upstash Redis REST URL for multi-container serverless persistence | `https://your-redis.upstash.io` |
| `UPSTASH_REDIS_REST_TOKEN` *(Optional)* | Upstash Redis REST Token | `your_upstash_token` |

> **Tip for Vercel Serverless**: If you enable free Upstash Redis (`UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN`), the gateway coordinates tasks across isolated serverless containers with 0% dropped tasks and 0 timeouts.

---

## 🔒 Security & Sandboxing

* **Boundary Protection**: The executor enforces strict root directory boundaries. Any attempt by the AI to access files outside your designated root (`../../etc/passwd` or `C:\Windows`) raises an immediate `PermissionError`.
* **Zero Inbound Ports**: Your computer never opens an incoming network port. All communication uses outbound HTTPS polling.
* **Process Isolation**: Terminal commands run inside isolated process groups with Windows `taskkill /F /T` tree-kill timeouts to prevent hanging child processes.

---

## 📄 License

MIT License. Open-source and free for personal and commercial use.
