# 🤖 AGENTS.md — Syntrak Developer & Agent Guidelines

Welcome to the **Syntrak** codebase. This document outlines the architectural patterns, development workflows, testing procedures, and coding guidelines for AI coding agents and human developers contributing to this project.

---

## 📌 Project Overview

**Syntrak** is an open-source, terminal-based and web-ready AI code reviewer and writer assistant. It provides multi-provider LLM orchestration, precision file editing, automated git snapshots with rollbacks, secure Google OAuth/JWT authentication, and a Neovim-styled (`syntrak.nvim`) web console.

### Tech Stack
- **Language**: Python 3.10+
- **CLI & REPL**: `typer`, `prompt-toolkit`, `rich`
- **Web API & Streaming**: `fastapi`, `uvicorn`, `httpx`, Server-Sent Events (SSE)
- **Database & Persistence**: `sqlalchemy` (>=2.0.0), `psycopg2-binary`, `sqlite3`
- **LLM Gateway & Tool Calling**: `litellm`, custom XML/JSON streaming parser
- **Validation & Settings**: `pydantic` (v2), `pydantic-settings`, `pyyaml`
- **Frontend**: Vanilla HTML5, Vanilla CSS3 (Custom properties, themes, Powerline glyphs), Vanilla JavaScript (ES6+ with `EventSource`)
- **Testing**: `pytest`, `pytest-asyncio`

---

## 🏗️ Codebase Structure

```text
Syntrak/
├── syntrak/
│   ├── __init__.py
│   ├── cli.py                  # Typer CLI entry points (syntrak, syntrak serve, review)
│   ├── config.py               # Pydantic settings, hierarchical .env loader, YAML configs
│   ├── core/                   # Orchestration engine
│   │   ├── agent.py            # ReAct agent loop (Reasoning + Action)
│   │   ├── context.py          # Workspace file trees, git status, active branch context
│   │   ├── events.py           # Typed SSE & terminal event definitions
│   │   ├── memory.py           # Token-aware sliding window conversation memory
│   │   ├── prompt.py           # Dynamic system prompts and tool instruction formatting
│   │   └── session.py          # SessionManager coordinating memory, tools, and LLM state
│   ├── llm/                    # Model interface & parsing
│   │   ├── base.py             # LLM client abstractions
│   │   ├── litellm_client.py   # Unified LiteLLM client (Ollama, NVIDIA, OpenRouter, OpenAI, etc.)
│   │   └── parser.py           # Robust XML (<tool_call>) and JSON tool call parser
│   ├── server/                 # Web server & persistence
│   │   ├── app.py              # FastAPI server, SSE stream (/api/chat/stream), REST routes
│   │   ├── auth.py             # Google OAuth verification & JWT cookie/header session handler
│   │   ├── db.py               # SQLAlchemy 2.0 ORM models (UserModel, ConversationModel, MessageModel)
│   │   ├── schemas.py          # FastAPI Pydantic request/response schemas
│   │   └── static/             # Neovim-themed web dashboard (HTML/CSS/JS)
│   ├── tools/                  # Tool execution engine
│   │   ├── base.py             # ToolRegistry and tool decorator
│   │   ├── bash_ops.py         # Workspace-bounded shell execution
│   │   ├── file_ops.py         # read_file, write_file, replace_in_file, list_dir
│   │   ├── git_ops.py          # git_diff, git_status, snapshot & rollback (/undo)
│   │   └── review_ops.py       # Automated PR / git diff reviewer
│   └── ui/                     # Terminal UI
│       ├── commands.py         # REPL slash command handlers (/review, /diff, /undo, /model)
│       ├── renderer.py         # Rich markdown, diffs, and event stream formatting
│       └── repl.py             # Interactive prompt_toolkit REPL
├── tests/                      # Pytest unit and integration test suite
├── pyproject.toml              # Packaging, metadata, and dependencies
├── ARCHITECTURE.md             # Detailed architecture diagrams & roadmap
└── README.md                   # Public documentation & user quickstart
```

---

## 🛠️ Development & Environment Setup

### 1. Virtual Environment
Always use the local virtual environment:
```bash
# Activation
source .venv/bin/activate

# Running tests
pytest
# or explicitly:
.venv/bin/pytest
```

### 2. Dependency Management
- Dependencies are defined in `pyproject.toml` under `[project.dependencies]`.
- When adding a new library:
  1. Add the package to `pyproject.toml`.
  2. Install via `.venv/bin/pip install "<package>"`.
  3. Verify tests with `.venv/bin/pytest`.

---

## 🧪 Testing Guidelines

- Test files reside in the `tests/` directory:
  - `test_agent.py`: Agent ReAct cycle execution.
  - `test_config.py`: Configuration loading, `.env` parsing, and secret resolution.
  - `test_conversations.py`: SQLAlchemy database CRUD, sessions, cascades, and FastAPI conversation/auth endpoints.
  - `test_file_ops.py`: File reading, writing, and `replace_in_file` search-and-replace.
  - `test_memory.py`: Conversation memory trimming and context sliding windows.
  - `test_parser.py`: XML and JSON tool call parser edge cases.
  - `test_server.py`: FastAPI server status, model switching, and diff endpoints.
- **Run all tests**:
  ```bash
  .venv/bin/pytest -v
  ```
- Any new features, endpoints, or tools **must** be accompanied by unit tests.

---

## 🛡️ Coding & Architectural Conventions

1. **SQLAlchemy 2.0 Best Practices**:
   - Use `DeclarativeBase`, `Mapped[...]`, `mapped_column(...)`, and typed queries (`select()`, `session.scalars()`, `session.get()`).
   - Use the `Database.get_session()` context manager for transaction boundaries (`commit`/`rollback`).
   - Handle database driver fallbacks gracefully (e.g. falling back to SQLite if PostgreSQL driver is unavailable).
2. **Safe Code Editing (`replace_in_file`)**:
   - The file modification tool relies on precise unique target substrings to prevent hallucinated rewrites.
3. **Git Snapshots & Checkpoints**:
   - Mutating tool actions should integrate with `create_snapshot()` so users can invoke `/undo` to revert unwanted changes.
4. **FastAPI & SSE Streaming**:
   - Event models inherit from `pydantic.BaseModel` in `syntrak/core/events.py`.
   - Streaming endpoints yield SSE-formatted lines (`data: <json>\n\n`).
5. **No Blind Secrets**:
   - Never hardcode API keys or tokens in code or test fixtures.
   - Use `syntrak.config.load_env_file()` and environment variables.
