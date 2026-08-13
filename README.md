# 🎓 Syntrak

> **Terminal-based and web-ready open-source code reviewer & writer assistant**  
> Inspired by Claude Code and OpenCode / Aider, built in Python for local and cloud open-source models.

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Live Demo](https://img.shields.io/badge/Live%20Demo-syntrak.harsh--shah.me-2ea44f.svg)](https://syntrak.harsh-shah.me)

🌐 **Live Demo**: [https://syntrak.harsh-shah.me](https://syntrak.harsh-shah.me) | 📐 **[Architecture & Implementation Plan](ARCHITECTURE.md)**

---

## ✨ Features

- 🧠 **Multi-Provider & Cloud Model Support**: Works seamlessly with **Ollama**, **NVIDIA NIM**, **OpenRouter**, **vLLM**, **LM Studio**, **OpenAI**, **Anthropic Claude**, **Google Gemini**, **Groq**, or any OpenAI-compatible API.
- ⚡ **Interactive Terminal REPL**: Built on `prompt_toolkit` and `rich` with command auto-completion, history navigation, streaming markdown, and collapsible tool execution panels.
- 💻 **Neovim & Tmux Monospace Web Console**: Built-in high-density developer dashboard (`syntrak.nvim`) running in your browser with live buffer tabs, statuslines, and 5 classic color schemes.
- 🔍 **Automated Code Reviewer**: Run `/review` or `syntrak review` to inspect git diffs for bugs, security vulnerabilities, edge cases, and actionable code fixes.
- ✏️ **Targeted Code Writer**: Intelligent search-and-replace chunk editing (`replace_in_file`), whole-file manipulation, and safe execution bounds.
- 🛡️ **Safety & Git Rollback**: Automatic checkpointing via git snapshots allows you to `/undo` changes safely.
- 🌐 **Web Extension Ready**: Event-driven streaming architecture with built-in FastAPI backend (`syntrak serve`) providing Server-Sent Events (SSE) and REST APIs for web-based dashboards.

---

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/enky-yy/Syntrak.git
cd Syntrak

# Create virtual environment and install in editable mode
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Start the Interactive REPL

```bash
# Start with default local model (Ollama)
syntrak

# Or launch with a specific model / endpoint
syntrak --model ollama/qwen2.5-coder:latest
syntrak --model openai/meta/llama-3.1-8b-instruct --api-base https://integrate.api.nvidia.com/v1 --api-key nvapi-xxxx
```

---

## 💻 Web UI Console (`syntrak.nvim`)

Try the live online demo at **[https://syntrak.harsh-shah.me](https://syntrak.harsh-shah.me)** or run it locally:

```bash
syntrak serve --port 8000
```
Open **[http://localhost:8000](http://localhost:8000)** (or your custom domain) to access the developer workspace.

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
- `[ 1: agent.buf ]` — Real-time interactive AI chat with terminal prompt formatting and streaming code outputs.
- `[ 2: review.diff ]` — Automated code review buffer for PR and diff audits.
- `[ 3: config.lua ]` — Live model and provider configuration editor.

---

## ☁️ Configuring Cloud-Based & Hosted Models

Syntrak uses [LiteLLM](https://github.com/BerriAI/litellm) under the hood, enabling seamless integration with any cloud LLM provider or OpenAI-compatible endpoint.

### 1. Provider Examples & Formatting

| Provider | Model Identifier | API Base URL | API Key Source |
| :--- | :--- | :--- | :--- |
| **NVIDIA NIM** | `openai/meta/llama-3.1-8b-instruct`<br>`openai/deepseek-ai/deepseek-r1`<br>`openai/meta/llama-3.3-70b-instruct` | `https://integrate.api.nvidia.com/v1` | `NVIDIA_API_KEY` or `--api-key` |
| **OpenRouter** | `openrouter/anthropic/claude-3.5-sonnet`<br>`openrouter/deepseek/deepseek-r1`<br>`openrouter/meta-llama/llama-3.3-70b-instruct` | `https://openrouter.ai/api/v1` (optional) | `OPENROUTER_API_KEY` |
| **Groq** | `groq/llama-3.3-70b-versatile`<br>`groq/mixtral-8x7b-32768` | Default / Managed | `GROQ_API_KEY` |
| **OpenAI** | `openai/gpt-4o`<br>`openai/gpt-4o-mini`<br>`openai/o3-mini` | Default / Managed | `OPENAI_API_KEY` |
| **Anthropic** | `anthropic/claude-3-5-sonnet-20241022` | Default / Managed | `ANTHROPIC_API_KEY` |
| **Google Gemini** | `gemini/gemini-2.0-flash`<br>`gemini/gemini-1.5-pro` | Default / Managed | `GEMINI_API_KEY` |
| **vLLM / LocalAI** | `openai/<model-name>` | `http://localhost:8000/v1` | Optional |
| **Ollama** | `ollama/qwen2.5-coder:latest`<br>`ollama/deepseek-coder-v2` | `http://localhost:11434` | Not required |

---

### 2. Where to Configure Your Cloud Model

You can configure your model using any of the following methods (in order of precedence):

#### Method A: Global Config File (`~/.syntrak/config.yaml`)
Run `syntrak init` to create the global configuration file at `~/.syntrak/config.yaml`:

```yaml
llm:
  model: "openai/meta/llama-3.1-8b-instruct"
  api_base: "https://integrate.api.nvidia.com/v1"
  api_key: "nvapi-your-key-here"
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

#### Method B: Project Workspace Config (`.syntrakrc.yaml`)
Create a `.syntrakrc.yaml` file in the root of any repository to define per-project model configurations and custom instructions:

```yaml
llm:
  model: "openai/gpt-4o"
  api_key: "sk-proj-xxxx"

custom_instructions: |
  Always follow PEP 8 and write type annotations for all function parameters.
```

#### Method C: Environment Variables (`.env` or shell export)
Export provider API keys in your terminal profile or `.env` file:

```bash
# NVIDIA NIM
export NVIDIA_API_KEY="nvapi-xxxx"

# OpenAI
export OPENAI_API_KEY="sk-proj-xxxx"

# Anthropic
export ANTHROPIC_API_KEY="sk-ant-xxxx"

# OpenRouter
export OPENROUTER_API_KEY="sk-or-xxxx"

# Groq
export GROQ_API_KEY="gsk_xxxx"
```

#### Method D: CLI Command-Line Flags
Pass flags directly when launching Syntrak:

```bash
syntrak --model openai/meta/llama-3.1-8b-instruct --api-base https://integrate.api.nvidia.com/v1 --api-key nvapi-xxxx
```

#### Method E: Inside the Web UI (`http://localhost:8000`)
1. Start the web server: `syntrak serve --port 8000`
2. Navigate to the **`config.lua`** tab (or type `:config` in the command prompt).
3. Select a preset (Ollama, NVIDIA NIM, DeepSeek-R1) or enter your custom model identifier, API Base URL, and API Key, then click **`:w (Save Settings)`**.

#### Method F: Live Switching in REPL (`/model`)
Switch models on the fly during an active terminal session:

```text
>>> /model openai/meta/llama-3.1-8b-instruct https://integrate.api.nvidia.com/v1 nvapi-xxxx
```

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
| `/clear` or `:clear` | Clear chat history / buffer |
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
syntrak serve --port 8000
```

---

## 🌐 Web Architecture & Endpoints

When running `syntrak serve --port 8000`, the following endpoints are available:
- `GET /`: Neovim / Tmux monospace developer dashboard.
- `POST /api/chat/stream`: Server-Sent Events (SSE) streaming real-time tokens, thoughts, and tool execution status.
- `GET /api/session/status`: Active session metadata and git status.
- `POST /api/model`: Switch active model and API base dynamically.
- `GET /api/diff`: Return unified diffs for web-based diff viewers.
- `POST /api/undo`: Rollback changes via git snapshot.
- `POST /api/clear`: Reset conversation memory.

---

## 🧪 Running Tests

```bash
pytest
```

---

## 📄 License
MIT License.
