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

---

## ⚡ Global Multi-Project Mode (Connect ONCE, Use Lifetime)

Instead of running the bridge inside a specific folder, you can connect your **entire projects folder** (e.g. `C:\projects` or `~/projects`) once. Gemini and ChatGPT will be able to discover, switch between, and edit **any project on your computer** directly from the chat window!

### Option A: 1-Time Lifetime Install (Runs silently in the background on startup)

On Windows, run this **one time**:
```powershell
python bridge.py --install-startup --key "YOUR_SECRET_KEY" --root "C:\projects"
```
* That's it! It runs silently in the background on every Windows boot. No terminal windows, no restarts.
* *(To uninstall anytime, simply run `python bridge.py --uninstall-startup`)*.

---

### Option B: Run in Terminal for All Projects

```bash
python bridge.py --key "YOUR_SECRET_KEY" --root "C:\projects"
```

---

## 🤖 How You Interact with Gemini / ChatGPT (Multi-Project)

Once connected, you can manage all your projects directly in your chat:

* **Ask to see your projects**:
  > *"What projects do I have on my machine?"*
  > **Gemini**: *"Found 3 projects: `d4-workforce-management`, `ai-agent`, and `portfolio`."*

* **Ask to switch projects**:
  > *"Switch to `d4-workforce-management` and analyze `AllInbox.jsx`."*
  > **Gemini**: *"Switched active project to `d4-workforce-management`. Here is what `AllInbox.jsx` does..."*

* **Cross-project refactoring**:
  > *"Compare the database schema in `project-A` with `project-B` and edit `schema.prisma`."*

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
