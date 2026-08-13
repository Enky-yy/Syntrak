# 🎓 CampusCLI

> **Terminal-based and web-ready open-source code reviewer & writer assistant**  
> Inspired by Claude Code and OpenCode / Aider, built in Python for local and open-source models.

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## ✨ Features

- 🧠 **Open-Source LLM First**: Seamlessly works with **Ollama** (`ollama/qwen2.5-coder:32b`, `ollama/deepseek-coder-v2`), **vLLM**, **LM Studio**, **LocalAI**, **OpenRouter**, or any OpenAI-compatible API.
- ⚡ **Interactive Terminal REPL**: Built on `prompt_toolkit` and `rich` with command auto-completion, history navigation, streaming markdown, and collapsible tool execution panels.
- 🔍 **Automated Code Reviewer**: Run `/review` or `campuscli review` to inspect git diffs for bugs, security vulnerabilities, edge cases, and actionable code fixes.
- ✏️ **Targeted Code Writer**: Intelligent search-and-replace chunk editing (`replace_in_file`), whole-file manipulation, and safe execution bounds.
- 🛡️ **Safety & Git Rollback**: Automatic checkpointing via git snapshots allows you to `/undo` changes safely.
- 🌐 **Web Extension Ready**: Event-driven streaming architecture with built-in FastAPI backend (`campuscli serve`) providing Server-Sent Events (SSE) and REST APIs for a future React/Web UI.

---

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/enky-yy/CampusCLI.git
cd CampusCLI

# Create virtual environment and install in editable mode
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Start the Interactive REPL

```bash
# Start with default Ollama model
campuscli

# Or specify your local open-source model
campuscli --model ollama/qwen2.5-coder:latest
campuscli --model ollama/deepseek-coder-v2 --api-base http://localhost:11434
```

---

## ⌨️ Interactive Slash Commands

Inside the REPL, type `/` to see autocompletions:

| Command | Description |
| :--- | :--- |
| `/review` | Perform automated code review on current diff (unstaged/staged) |
| `/diff` | Render syntax-highlighted git diff |
| `/commit` | Generate a Conventional Commit message and commit changes |
| `/model [name]` | View active model or switch to a new model on the fly |
| `/undo` | Rollback to the previous git checkpoint |
| `/compact` | Summarize and compact conversation memory |
| `/clear` | Clear chat history |
| `/config` | Print active configuration and endpoint settings |
| `/help` | Show command menu |
| `/exit` | Exit the session |

---

## 🛠️ CLI Usage & Automation

CampusCLI also supports headless execution for scripts and CI/CD pipelines:

```bash
# Non-interactive query
campuscli run "Add unit tests for the auth module"

# Automated code review against working changes
campuscli review

# Review against a specific target branch
campuscli review --target-branch main

# View syntax-highlighted diff
campuscli diff

# Start the Web API Server for browser frontends
campuscli serve --port 8000
```

---

## ⚙️ Configuration

Generate a global configuration file:
```bash
campuscli init
```
This writes to `~/.campuscli/config.yaml`:

```yaml
llm:
  model: "ollama/qwen2.5-coder:latest"
  api_base: "http://localhost:11434"
  api_key: null
  temperature: 0.2
  max_tokens: 4096
  context_window: 32768
  force_xml_tools: false

security:
  require_confirmation_for_bash: true
  blocked_commands:
    - "rm -rf /"
    - "mkfs"
  max_bash_timeout_seconds: 60

max_agent_steps: 25
enable_git_snapshots: true
```

---

## 🌐 Web Architecture & Extension

CampusCLI is designed from day one to power both terminal and browser interfaces.

When running `campuscli serve --port 8000`, the following endpoints are available:
- `POST /api/chat/stream`: Server-Sent Events (SSE) streaming real-time tokens, thoughts, and tool execution status.
- `GET /api/session/status`: Active session metadata and git status.
- `POST /api/model`: Switch active model and API base dynamically.
- `GET /api/diff`: Return unified diffs for web-based diff viewers.
- `POST /api/undo`: Rollback changes.

---

## 🧪 Running Tests

```bash
pytest
```

---

## 📄 License
MIT License.
