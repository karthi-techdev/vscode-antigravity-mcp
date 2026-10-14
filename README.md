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

## 🌐 Connection Details (At a Glance)

Connect any MCP-compatible AI client to your local workspace using these hosted endpoints:

| Parameter | Value |
|---|---|
| **Hosted Server URL** | `https://vscode-antigravity-mcp.vercel.app` |
| **MCP SSE Endpoint** | `https://vscode-antigravity-mcp.vercel.app/mcp/sse` |
| **Complete Connection URL** | `https://vscode-antigravity-mcp.vercel.app/mcp/sse?token=YOUR_SECRET_KEY` |
| **Auth Options** | Query Parameter (`?token=YOUR_SECRET_KEY`) or Header (`Authorization: Bearer YOUR_SECRET_KEY`) |
| **Your Secret Key** | Any private passphrase you choose (e.g. `karthi_secure_2026`). **Zero server pre-registration required!** |
| **Protocol** | Model Context Protocol (MCP) via Server-Sent Events (SSE) |

---

## ⚡ Step-by-Step Setup Guide (ZERO Git Cloning Required)

You do **NOT** need to clone this repository. You only need the single [`bridge.py`](https://vscode-antigravity-mcp.vercel.app/bridge.py) helper file on your machine.

---

### Step 1: Download `bridge.py`

Open your terminal in your root projects folder (e.g. `C:\projects` or `~/projects`) or any individual repository:

#### Windows (PowerShell):
```powershell
curl.exe -o bridge.py https://vscode-antigravity-mcp.vercel.app/bridge.py
```

#### macOS / Linux:
```bash
curl -o bridge.py https://vscode-antigravity-mcp.vercel.app/bridge.py
```

---

### Step 2: Start the Local Bridge

Choose **any private key** you want (e.g. `--key "my_secret_key_123"`).

#### 🌟 Option A: 1-Time Lifetime Install (Runs in the background on startup)
On Windows, run this **one time**:
```powershell
python bridge.py --install-startup --key "YOUR_SECRET_KEY" --root "C:\projects"
```
* **Silent & Automatic**: Starts in the background on every Windows boot.
* No open terminal windows, no maintenance.
* *(To uninstall anytime: `python bridge.py --uninstall-startup`)*

#### 💻 Option B: Run in Current Terminal
```bash
python bridge.py --key "YOUR_SECRET_KEY" --root "C:\projects"
```

Once started, the bridge securely connects outbound to the Vercel gateway and waits for commands.

---

### Step 3: Connect Your AI Assistant

Choose your AI platform below and follow the quick setup steps:

#### 🟣 Claude Desktop
Claude Desktop connects to remote SSE MCP servers using `mcp-remote`.

1. Open your Claude Desktop configuration file:
   * **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
   * **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
2. Add the `antigravity-ide` server under `"mcpServers"`:
   ```json
   {
     "mcpServers": {
       "antigravity-ide": {
         "command": "npx",
         "args": [
           "-y",
           "mcp-remote",
           "https://vscode-antigravity-mcp.vercel.app/mcp/sse?token=YOUR_SECRET_KEY"
         ]
       }
     }
   }
   ```
3. Restart Claude Desktop. You will see a hammer icon 🔨 with all **17 IDE tools** ready to use!

---

#### 🟢 ChatGPT (Web & Custom GPTs)
You can connect ChatGPT Plus / Team / Enterprise via **Custom GPT Actions** or browser MCP plugins:

##### Using Custom GPT Actions:
1. Go to [chatgpt.com](https://chatgpt.com) ➔ **Explore GPTs** ➔ **Create a GPT**.
2. Click **Configure** tab ➔ Scroll down and click **Create new action**.
3. Under **Authentication**:
   * **Authentication Type**: `API Key`
   * **Auth Type**: `Bearer`
   * **API Key**: Enter your `YOUR_SECRET_KEY`.
4. Under **Import from URL / Schema**:
   * Enter: `https://vscode-antigravity-mcp.vercel.app/mcp/sse?token=YOUR_SECRET_KEY`
5. Save the GPT and start chatting!

##### Using ChatGPT MCP Browser Connectors / Extensions:
* **Server URL**: `https://vscode-antigravity-mcp.vercel.app/mcp/sse?token=YOUR_SECRET_KEY`
* **Transport**: `SSE`

---

#### 🔵 Gemini Web & Google Antigravity IDE

##### In Google Antigravity IDE:
Add the remote MCP bridge to your global or workspace `mcp_config.json` (`~/.gemini/antigravity-ide/mcp_config.json`):
```json
{
  "mcpServers": {
    "antigravity-remote": {
      "url": "https://vscode-antigravity-mcp.vercel.app/mcp/sse?token=YOUR_SECRET_KEY"
    }
  }
}
```

##### In Gemini Web (via MCP Web Extension):
* **Endpoint**: `https://vscode-antigravity-mcp.vercel.app/mcp/sse?token=YOUR_SECRET_KEY`
* **Auth**: Pass your key in the `Authorization: Bearer YOUR_SECRET_KEY` header or query parameter.

---

#### 🟡 Cursor & VS Code (Cline, Roo Code, Continue.dev)

##### In Cline / Roo Code (VS Code Extension):
1. Click the **MCP Servers** (network plug) icon in the Cline/Roo Code sidebar.
2. Click **Add New MCP Server** or open `cline_mcp_settings.json`:
   ```json
   {
     "mcpServers": {
       "antigravity-ide": {
         "url": "https://vscode-antigravity-mcp.vercel.app/mcp/sse?token=YOUR_SECRET_KEY",
         "type": "sse"
       }
     }
   }
   ```

##### In Continue.dev (`~/.continue/config.json`):
```json
{
  "mcpServers": [
    {
      "name": "antigravity-ide",
      "url": "https://vscode-antigravity-mcp.vercel.app/mcp/sse?token=YOUR_SECRET_KEY"
    }
  ]
}
```

---

### Step 4: Chat and Control Your Workspace!

Now simply ask your AI assistant naturally in the chat:

* **Discover & switch projects**:
  > *"What projects do I have on my computer?"*
  > *"Switch active project to `my-web-app`."*

* **Read & modify files**:
  > *"Read `src/App.tsx` and explain how authentication is implemented."*
  > *"Add a new modal component in `src/components/Modal.tsx`."*

* **Run Git commands**:
  > *"Check git status and show me what changed in the last commit."*
  > *"Create a new git branch called `feature/mcp-integration`."*

* **Run PowerShell / CMD commands**:
  > *"Run `npm test` using PowerShell and tell me if all tests pass."*
  > *"Execute `git log -n 3` and summarize recent work."*

---

## 🛠️ Complete Tools Reference (17 Tools)

### 📂 Multi-Project & Workspace Navigation
| Tool | Description |
|---|---|
| `list_projects()` | Discovers and lists all project folders, detected tech stacks, and Git branches across your system. |
| `set_active_project(project_name)` | Switches active project context to a different folder on your machine. |
| `get_active_project()` | Inspects current active project name, workspace path, and Git status. |
| `get_workspace_context()` | Queries overview of active workspace, Git branch, and working changes. |

### 📝 File & Directory Operations
| Tool | Description |
|---|---|
| `read_workspace_file(path, [max_lines], [start_line], [project])` | Reads lines or full contents of any file with line numbering. |
| `write_workspace_file(path, content, [project])` | Creates or replaces files in your workspace. |
| `edit_workspace_file(path, old_str, new_str, [project])` | Finds and replaces specific code blocks in a file. |
| `create_directory(path, [project])` | Creates a new directory (and any necessary parent directories). |
| `delete_file(path, [recursive], [project])` | Deletes a file or directory (with `recursive=True` for directories). |
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
| `run_powershell_command(command, [timeout_seconds], [project])` | Native PowerShell command or script execution with full UTF-8 encoding support. |
| `run_cmd_command(command, [timeout_seconds], [project])` | Windows Command Prompt (`cmd.exe`) command and batch script execution. |
| `run_git_command(subcommand, [timeout_seconds], [project])` | Direct Git operations (`status`, `diff`, `log`, `branch`, `commit`, `push`, `pull`, etc.). |
| `run_terminal_command(command, [timeout_seconds], [project])` | Default system terminal command execution with configurable timeout. |

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
