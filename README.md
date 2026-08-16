# 🎓 Syntrak

> **Terminal-based and web-ready open-source code reviewer & writer assistant**  
> Inspired by Claude Code and OpenCode / Aider, built in Python for local and cloud open-source models.

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/version-0.2.0-green.svg)](https://github.com/enky-yy/Syntrak)
[![Live Demo](https://img.shields.io/badge/Live%20Demo-syntrak.harsh--shah.me-2ea44f.svg)](https://syntrak.harsh-shah.me)

🌐 **Live Demo**: [https://syntrak.harsh-shah.me](https://syntrak.harsh-shah.me) | 📐 **[Architecture & Implementation Plan](ARCHITECTURE.md)**

---

## ✨ Features

- 🧠 **Multi-Provider & Cloud Model Support**: Works seamlessly with **Ollama**, **NVIDIA NIM**, **OpenRouter**, **vLLM**, **LM Studio**, **OpenAI**, **Anthropic Claude**, **Google Gemini**, **Groq**, or any OpenAI-compatible API.
- ⚡ **Dual Operating Modes**:
  - **Chat Mode** *(Default)*: Clean, neutral conversational AI (like ChatGPT) for answering programming questions, architecture discussions, and algorithm design without tool clutter.
  - **Agent Mode**: Full autonomous repo workspace operations with targeted search-and-replace edits (`replace_in_file`), bash commands, and git checkpoints.
- 📱 **Multi-Device & Responsive Web Console**: Complete mobile, tablet, and desktop layout optimization with slide-over drawer navigation, touch-friendly command line, backdrop blur, adaptive Powerline statusline, and responsive modal dialogues.
- 🔗 **GitHub Repository Connection**: Connect and clone remote GitHub repositories dynamically with custom branch checkout and branch tracking directly inside the web interface.
- 🛡️ **Safety & Policy Guardrails Engine**: Dedicated multi-layered security filter (`syntrak.core.guardrails`) that intercepts prompt injections, jailbreaks, secret exfiltration, malicious shell commands, and malware generation.
- 💻 **Neovim & Tmux Monospace Web Console**: High-density developer dashboard (`syntrak.nvim`) running in your browser with buffer tabs, statusline diagnostics, animated thinking pulses, and 5 classic color schemes.
- 🔐 **Google OAuth 2.0 & JWT Sessions**: Secure Google Sign-In with persistent user profiles, avatars, and JWT cookie/header authorization.
- 💬 **Multi-Thread Chat History**: Collapsible sidebar with date grouping (*Today*, *Yesterday*, *Previous 7 Days*, *Older*), real-time thread search, inline renaming, deletion, and full multi-turn conversation recovery.
- 🗄️ **Multi-Database Support (PostgreSQL & SQLite)**: Scalable SQLAlchemy 2.0 ORM persistence with automatic migrations and connection pooling.
- 🔍 **Automated Code Reviewer**: Run `/review` or `syntrak review` to inspect working diffs for bugs, security vulnerabilities, edge cases, and actionable code fixes.
- ✏️ **Targeted Code Writer**: Intelligent search-and-replace chunk editing (`replace_in_file`), whole-file manipulation, and workspace containment.
- 🛡️ **Git Snapshots & Instant Rollback**: Automatic checkpointing via git snapshots allows you to `/undo` changes safely.
- 🔒 **Zero-Leak Secret Management**: Automated `.env` file discovery with prioritized environment overrides and `.env.example` templates.
- 🌐 **Server-Sent Events (SSE) Streaming**: Real-time token and event streaming with live Markdown rendering and syntax highlighting.

---

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/enky-yy/Syntrak.git
cd Syntrak

# Create virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Configure Environment & Secrets (`.env`)

Copy the template and set your API keys or database credentials:

```bash
cp .env.example .env
```

```ini
# Google OAuth 2.0 Client ID for Web UI (Optional)
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com

# LLM Model & Endpoint (e.g. NVIDIA NIM, OpenRouter, OpenAI, Ollama)
LLM_MODEL=openai/nvidia/nemotron-3-ultra-550b-a55b
LLM_API_BASE=https://integrate.api.nvidia.com/v1

# Provider API Keys
OPENAI_API_KEY=nvapi-your-key-here
NVIDIA_API_KEY=nvapi-your-key-here

# Optional: PostgreSQL Database URL (falls back to local SQLite)
DATABASE_URL=postgresql://user:password@localhost:5432/syntrak_db
```

### 3. Start the Interactive REPL or Web Dashboard

```bash
# Launch Terminal REPL
syntrak

# Or start the Web Dashboard & API Server
syntrak serve --port 9000
```

---

## 💻 Web UI Console (`syntrak.nvim`)

Try the live online demo at **[https://syntrak.harsh-shah.me](https://syntrak.harsh-shah.me)** or run locally:

```bash
syntrak serve --port 9000
```
Open **[http://localhost:9000](http://localhost:9000)** to access the developer console.

### 🎨 Built-in Color Schemes
Switch color schemes instantly using the **`:colorscheme`** selector or by typing `:colorscheme <name>` in the prompt bar:

| Theme | Command | Aesthetic |
| :--- | :--- | :--- |
| **Gruvbox Dark** *(Default)* | `:colorscheme gruvbox` | Classic warm retro hacker palette (charcoal, amber, green, terracotta) |
| **Nord** | `:colorscheme nord` | Arctic frost slate with ice blues and snow white |
| **Tokyo Night** | `:colorscheme tokyonight` | Deep night sky indigo with electric cyan and violet |
| **Monokai Pro** | `:colorscheme monokai` | High-contrast hacker theme with vibrant yellow and green |
| **Solarized Dark** | `:colorscheme solarized` | Precision optical low-contrast dark teal & cyan |

### 📑 Bufferline Tabs & Navigation
- `[ 1: agent.buf ]` — Real-time interactive AI chat with terminal prompt formatting, animated `thinking...` indicator, and streaming code blocks.
- `[ 2: config.lua ]` — Live model and provider configuration editor.

---

## ☁️ Configuring Cloud & Local Models

Syntrak uses [LiteLLM](https://github.com/BerriAI/litellm) under the hood, enabling seamless integration with any cloud LLM provider or local OpenAI-compatible endpoint.

### 1. Provider Examples & Formatting

| Provider | Model Identifier | API Base URL | API Key Source |
| :--- | :--- | :--- | :--- |
| **NVIDIA NIM** | `openai/nvidia/nemotron-3-ultra-550b-a55b`<br>`openai/meta/llama-3.3-70b-instruct` | `https://integrate.api.nvidia.com/v1` | `NVIDIA_API_KEY` or `--api-key` |
| **OpenRouter** | `openrouter/anthropic/claude-3.5-sonnet`<br>`openrouter/deepseek/deepseek-r1` | `https://openrouter.ai/api/v1` (optional) | `OPENROUTER_API_KEY` |
| **Groq** | `groq/llama-3.3-70b-versatile`<br>`groq/mixtral-8x7b-32768` | Default / Managed | `GROQ_API_KEY` |
| **OpenAI** | `openai/gpt-4o`<br>`openai/gpt-4o-mini`<br>`openai/o3-mini` | Default / Managed | `OPENAI_API_KEY` |
| **Anthropic** | `anthropic/claude-3-5-sonnet-20241022` | Default / Managed | `ANTHROPIC_API_KEY` |
| **Google Gemini** | `gemini/gemini-2.0-flash`<br>`gemini/gemini-1.5-pro` | Default / Managed | `GEMINI_API_KEY` |
| **vLLM / LocalAI** | `openai/<model-name>` | `http://localhost:8000/v1` | Optional |
| **Ollama** | `ollama/qwen2.5-coder:latest`<br>`ollama/deepseek-coder-v2` | `http://localhost:11434` | Not required |

---

### 2. Configuration Hierarchy

Configure your model using any of the following methods (in order of precedence):

1. **CLI Command-Line Flags**: `syntrak --model <name> --api-base <url>`
2. **Project Workspace Config (`.syntrakrc.yaml`)**: Custom instructions and model preferences per repository.
3. **Global Config File (`~/.syntrak/config.yaml`)**: User-wide default preferences initialized via `syntrak init`.
4. **Environment Variables (`.env` or shell export)**: `LLM_MODEL`, `LLM_API_BASE`, `OPENAI_API_KEY`, etc.
5. **Web UI Config Buffer (`config.lua`)**: Interactive real-time switching in the web dashboard.

---

## ⌨️ Interactive Commands & Keybindings

Inside the REPL or Web Console, type `/` or `:` to see available commands:

| Command | Description |
| :--- | :--- |
| `/review` or `:Review` | Perform automated code review on current diff (unstaged/staged) |
| `/diff` | Render syntax-highlighted git diff |
| `/commit` | Generate a Conventional Commit message and commit changes |
| `/model [name]` | View active model or switch to a new model on the fly |
| `/undo` or `:Undo` | Rollback to the previous git checkpoint |
| `/compact` | Summarize and compact conversation memory |
| `/clear` or `:clear` | Clear chat history / reset buffer to splash screen |
| `:colorscheme [theme]` | Switch Web UI theme (`gruvbox`, `nord`, `tokyonight`, `monokai`, `solarized`) |
| `/config` or `:config` | Print active configuration and endpoint settings |
| `/help` or `:help` | Show command menu |
| `/exit` | Exit the session |

---

## 🛠️ CLI Headless Usage & Automation

Syntrak supports headless execution for scripts and CI/CD pipelines:

```bash
# Non-interactive query
syntrak run "Add unit tests for the auth module"

# Automated code review against working changes
syntrak review

# Review against a specific target branch
syntrak review --target-branch main

# View syntax-highlighted diff
syntrak diff

# Start the Web API Server for browser frontends
syntrak serve --port 9000
```

---

## 🌐 Web Architecture & Endpoints

When running `syntrak serve --port 9000`, the following endpoints are available:
- `GET /`: Neovim / Tmux monospace developer dashboard with Google Sign-In and chat history.
- `POST /api/auth/google`: Authenticate via Google Identity Services ID token and receive JWT session cookie.
- `POST /api/auth/logout`: Log out user and revoke session cookies.
- `GET /api/auth/me`: Get active user profile and metadata.
- `GET /api/conversations`: Retrieve user's conversation threads list.
- `POST /api/conversations`: Create a new conversation thread.
- `GET /api/conversations/{id}`: Fetch historical messages and reasoning events for a thread.
- `PATCH /api/conversations/{id}`: Rename conversation title.
- `DELETE /api/conversations/{id}`: Delete a conversation thread.
- `POST /api/chat/stream`: Server-Sent Events (SSE) streaming real-time tokens with automatic database persistence.
- `GET /api/session/status`: Active session metadata, active model, workspace root, and git status.
- `POST /api/repo/connect`: Clone or checkout a GitHub repository for Agent Mode.
- `GET /api/repo/info`: Retrieve active repository metadata and branch.
- `POST /api/model`: Switch active model and API base dynamically.
- `GET /api/diff`: Return unified diffs for web-based diff viewers.
- `POST /api/undo`: Rollback changes via git snapshot.

---

## 🧪 Running Tests

```bash
# Run the complete test suite
pytest -v
```

---

## 📄 License
**[MIT License](LICENSE)**
