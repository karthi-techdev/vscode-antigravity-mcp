# Universal Local IDE & Workspace MCP Bridge 🚀

> Connect Web AI assistants (**Gemini Web, ChatGPT, Claude**) directly and securely to **ANY local IDE or developer workspace** (**VS Code, Cursor, Windsurf, JetBrains / IntelliJ / PyCharm, Antigravity, Zed, Neovim, Terminal**) — with multi-user isolation, zero open ports, and hosted on **Vercel**.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-Protocol-purple.svg)](https://modelcontextprotocol.io)
[![FastMCP](https://img.shields.io/badge/FastMCP-v4.1.0-green.svg)](https://github.com/jlowin/fastmcp)
[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/karthi-techdev/vscode-antigravity-mcp)

---

## 💡 How It Works

Cloud AI models (Gemini Web, ChatGPT) cannot directly reach into your computer because of firewalls and Wi-Fi routers (NAT). 

**Universal IDE MCP Bridge** creates a secure outbound tunnel between your local projects (open in any IDE or terminal) and the cloud:

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

## 🌐 Web Connection Details (At a Glance)

Connect any Web AI Chat in your browser to your local computer:

| Platform | Endpoint URL | Format / Protocol |
|---|---|---|
| **Google Gemini Web** *(Connected Apps)* | `https://vscode-antigravity-mcp.vercel.app/mcp` | **StreamableHTTP** (Official Gemini MCP format) |
| **ChatGPT Web** *(Custom GPTs)* | `https://vscode-antigravity-mcp.vercel.app/openapi.json` | **OpenAPI Schema Actions** |
| **Google AI Studio Web** | `https://vscode-antigravity-mcp.vercel.app/openapi.json` | **OpenAPI Function Calling** |
| **Claude Web / Browser Extensions** | `https://vscode-antigravity-mcp.vercel.app/sse/sse` | **SSE Stream** |
| **Authentication Header** | `Authorization: Bearer YOUR_SECRET_KEY` | Zero registration needed; enter your secret key |
| **URL Query Token Option** | `?token=YOUR_SECRET_KEY` | E.g., `https://.../mcp?token=YOUR_SECRET_KEY` |

---

## ⚡ 3-Step Setup (ZERO Git Cloning Required)

You do **NOT** need to clone this repository. You only need the single [`bridge.py`](https://vscode-antigravity-mcp.vercel.app/bridge.py) file on your machine.

---

### Step 1: Download `bridge.py`

Open your terminal in your root projects folder (e.g. `C:\projects` or `~/projects`) or any individual repo:

#### Windows (PowerShell):
```powershell
curl.exe -o bridge.py https://vscode-antigravity-mcp.vercel.app/bridge.py
```

#### macOS / Linux:
```bash
curl -o bridge.py https://vscode-antigravity-mcp.vercel.app/bridge.py
```

---

### Step 2: Start the Bridge on Your Computer

Choose **any private key** you want (e.g. `--key "my_secret_key_123"`).

#### 🌟 Option A: 1-Time Lifetime Install (Runs silently in background on startup)
On Windows, run this **one time**:
```powershell
python bridge.py --install-startup --key "YOUR_SECRET_KEY" --root "C:\projects"
```
* **Silent & Automatic**: Starts in the background on every Windows boot.
* Permanent access to all projects under `C:\projects` from any browser.
* *(To uninstall anytime: `python bridge.py --uninstall-startup`)*

#### 💻 Option B: Run in Current Terminal
```bash
python bridge.py --key "YOUR_SECRET_KEY" --root "C:\projects"
```

Once running, your local companion is ready to receive commands from your web browser!

---

### Step 3: Connect Your Web AI Assistant (Browser-Only)

Choose whichever Web AI chat you use in your browser:

---

#### 🟢 1. ChatGPT Web (`chatgpt.com`)
*No browser extensions required! Uses ChatGPT's official Custom GPT Actions.*

1. In your browser, open [chatgpt.com](https://chatgpt.com).
2. In the left sidebar, click **Explore GPTs** ➔ click **+ Create** (top right).
3. Select the **Configure** tab:
   * **Name**: `My Local PC Assistant`
   * **Instructions**:
     ```
     You are connected to my local computer. Use the available actions to explore my projects, read and edit files, and execute PowerShell and Git commands on my machine.
     ```
4. Scroll to the bottom and click **Create new action**:
   * Under **Authentication**:
     * **Authentication Type**: `API Key`
     * **Auth Type**: `Bearer`
     * **API Key**: Enter your `YOUR_SECRET_KEY`
   * Under **Schema**:
     * Click **Import from URL**
     * Enter: `https://vscode-antigravity-mcp.vercel.app/openapi.json`
     * Click **Import**
   * *ChatGPT will immediately import all 17 actions (`list_projects`, `read_workspace_file`, `write_workspace_file`, `run_powershell_command`, `run_git_command`, etc.)!*
5. Click **Create / Save** (top right) ➔ Select **Only me**.
6. Open your new GPT in `chatgpt.com` and start chatting directly with your local computer!

*(Or, if using a Chrome extension like "ChatGPT MCP Connector", simply paste `https://vscode-antigravity-mcp.vercel.app/mcp/sse?token=YOUR_SECRET_KEY` into the extension settings).*

---

#### 🔵 2. Gemini Web (`gemini.google.com` & Google AI Studio)

##### A. Gemini Web (`gemini.google.com`) - Native Connected Apps:
1. In your browser, open **[gemini.google.com](https://gemini.google.com)**.
2. Go to **Settings** ➔ **Connected apps** ➔ click **Connect to an MCP server**.
3. In **MCP server URL**, enter:
   ```text
   https://vscode-antigravity-mcp.vercel.app/mcp?token=YOUR_SECRET_KEY
   ```
4. Leave **Client ID** and **Client secret** blank (OAuth is not needed).
5. Click **Next** ➔ Gemini will discover and display all 17 actions ➔ Click **Connect**.
6. Open a **New Chat**, type `@Universal IDE Remote Bridge` (or `@`), and ask Gemini to inspect, edit, or run commands on any project!

##### B. Google AI Studio Web (`aistudio.google.com`) - Native Web Chat:
1. Open [aistudio.google.com](https://aistudio.google.com) in your browser and start a new chat.
2. In the right-hand panel under **Tools** ➔ enable **Function Calling**.
3. Import the OpenAPI schema: `https://vscode-antigravity-mcp.vercel.app/openapi.json`.
4. Add Header: `Authorization: Bearer YOUR_SECRET_KEY`.
5. Now chat with Gemini 1.5 Pro in your browser — it invokes actions directly on your local computer!

---

#### 🟣 3. Claude Web (`claude.ai`)
1. Open [claude.ai](https://claude.ai) in your browser.
2. Using any Web MCP extension for Chrome/Edge:
   * **Server URL**: `https://vscode-antigravity-mcp.vercel.app/mcp/sse?token=YOUR_SECRET_KEY`
   * **Transport**: `SSE`
3. Claude Web can now discover and run all 17 IDE tools directly on your computer!

---

### Step 4: Start Chatting & Controlling Your Projects from the Browser!

Once connected in your browser, ask your AI naturally in the chat window:

* **Browse projects on your computer**:
  > *"What projects do I have on my system?"*
  > **AI**: *"Found 4 projects under `C:\projects`: `my-web-app`, `ai-bot`, `backend-api`, and `portfolio`."*

* **Switch active project**:
  > *"Switch active project to `my-web-app` and tell me what tech stack it uses."*
  > **AI**: *"Switched active project to `my-web-app`. It's a React + Vite TypeScript project..."*

* **Read & modify files**:
  > *"Read `src/App.tsx` and add a new dark mode toggle component."*
  > **AI**: *"I've read `App.tsx` and modified the code to add the dark mode toggle."*

* **Run PowerShell & Terminal commands**:
  > *"Run `npm test` using PowerShell and tell me if all tests pass."*
  > **AI**: *"Executing PowerShell command... All tests passed!"*

* **Git Version Control**:
  > *"Run `git status` and commit my changes with message 'feat: add dark mode'."*
  > **AI**: *"Running `git status`... Changes staged and committed successfully."*

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
