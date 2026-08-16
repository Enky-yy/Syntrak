  # 📜 Changelog

All notable changes to the **Syntrak** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-08-16

### Added
- **Multi-Device & Responsive Design System**:
  - Comprehensive CSS media queries for desktop, tablet (`<=1024px`), mobile (`<=768px`), and small mobile phones (`<=480px`).
  - Mobile slide-over drawer navigation for `#chatSidebar` with smooth touch backdrop blur (`.sidebar-backdrop`).
  - Auto-closing sidebar drawer upon thread selection or new chat creation on touch devices.
  - Responsive ASCII banner scaling (`min(2.1vw, 8.5px)`) and single-column quick action chips for mobile screens.
  - Adaptive Powerline statusline hiding non-essential segments on narrow screens while preserving active mode, git branch, and LLM model info.
  - Touch-friendly command line textarea, action buttons, and responsive modal dialogs.
- **Security & Authorization Hardening**:
  - Ephemeral cryptographically random JWT secret generation in local mode (`secrets.token_urlsafe(32)`) and mandatory secret requirement in production.
  - Added user authentication dependencies (`Depends(get_current_user)`) across all state-mutating control endpoints (`/api/model`, `/api/diff`, `/api/undo`, `/api/clear`).
  - Added security response headers middleware (`X-Frame-Options: SAMEORIGIN`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `X-XSS-Protection`).
  - Added SSRF protection blocking internal cloud metadata services (`169.254.169.254`, `metadata.google.internal`) in custom API bases.
  - Excluded sensitive secret files from `search_files` and `list_directory` to prevent accidental credential indexing.
  - Enforced strict default workspace boundary containment on relative paths even when `SYNTRAK_WORKSPACE_ROOT` is unset.
  - Implemented in-memory sliding window rate limiter for expensive endpoints (`/api/chat/stream`, `/api/repo/connect`).
  - Added indirect prompt injection defenses wrapping external files and tool outputs in `<untrusted_file_content>` and `<untrusted_tool_output>` tags.
  - Added stream regex scrubber (`scrub_secrets`) masking API keys (`sk-...`, `ghp-...`, JWTs) from live token streams.
  - Disabled untrusted Git hooks execution during repository clone and workspace operations (`-c core.hooksPath=/dev/null`).
  - Enabled SQLite Write-Ahead Logging (`PRAGMA journal_mode=WAL;`) and concurrency busy timeout (`5000ms`) to eliminate database write lock contention.
  - Added HTTP request body payload size limiting middleware (rejecting payloads > 5 MB with HTTP 413).
  - Enforced 5 MB maximum file read and search inspection limit to prevent Out-Of-Memory (OOM) Denial of Service.
  - Implemented token revocation blocklist (`revoke_jwt_token`) upon `/api/auth/logout` preventing stateless JWT replay.
  - Added `Content-Security-Policy` and `Permissions-Policy` defensive HTTP response headers.
  - Added 30-second execution timeouts and `subprocess.TimeoutExpired` safety handlers to all git operations.
  - Hardened XML and Markdown tool parsers against ReDoS with maximum 1 MB scan buffer limits.
  - Partitioned guest sessions via custom `X-Guest-ID` and `syntrak_guest_id` cookies to prevent cross-tenant conversation collision.

### Changed
- Bumped project version to `0.2.0` across packaging, server metadata, and UI headers.

---

## [0.1.4] - 2026-08-16

### Added
- **Security Patches**:
  - Cryptographic validation for Google OAuth Identity Services tokens with unverified token rejection.
  - IDOR protection on conversation chat streaming and message fetching.
  - Stricter workspace boundary enforcement and bash regex command filters.

---


### Added
- **Developer Guidelines & Changelog**: Added `AGENTS.md` and `CHANGELOG.md` to the project root.
- **Resilient Database Driver Handling**: Added automatic SQLite fallback if `psycopg2` or remote database connection is unavailable.
- **Package Dependency**: Added `psycopg2-binary>=2.9.0` to core dependencies for seamless PostgreSQL support.

### Changed
- Refined Web UI statusline elements and footer host indicator in `syntrak.nvim`.

---

## [0.1.2] - 2026-08-15

### Added
- **SQLAlchemy 2.0 Persistence Layer**: Replaced raw SQLite driver with a modern, typed SQLAlchemy 2.0 ORM engine.
- **Declarative ORM Models**: Added `UserModel`, `ConversationModel`, and `MessageModel` with type-annotated columns (`Mapped`, `mapped_column`) and cascading relationships.
- **Multi-Database URL Support**: Dynamic connection string resolution supporting SQLite, PostgreSQL, and MySQL.
- **Automatic URL Normalization**: Added dialect normalization translating legacy `postgres://` URLs (used by cloud DB providers like Aiven and Supabase) to `postgresql://`.
- **Resilient Driver Fallback**: Built-in graceful degradation to local SQLite (`~/.syntrak/syntrak.db`) if remote database drivers (e.g. `psycopg2`) are unavailable or endpoints fail.
- **PostgreSQL Dependency**: Added `psycopg2-binary>=2.9.0` to package dependencies.
- **Agent Guidelines**: Added `AGENTS.md` containing developer and AI coding agent guidelines.

### Changed
- Refactored `syntrak/server/db.py` to use SQLAlchemy 2.0 select statements, scalar queries, and context-managed session handling (`get_session()`).
- Updated `pyproject.toml` dependencies with `sqlalchemy>=2.0.0` and `psycopg2-binary>=2.9.0`.
- Updated [ARCHITECTURE.md](ARCHITECTURE.md) to reflect multi-database SQLAlchemy architecture.

---

## [0.1.1] - 2026-08-15

### Added
- **Google OAuth 2.0 Authentication**: Seamless login via Google Identity Services (GIS) ID tokens with backend cryptographic validation.
- **JWT Session Security**: Secure session tokens stored in HTTP-only/SameSite cookies with automatic guest developer fallback.
- **ChatGPT-Style Sidebar History**:
  - Dynamic collapsible sidebar in `syntrak.nvim` web dashboard (`Ctrl+B` toggle).
  - Categorized date grouping (*Today*, *Yesterday*, *Previous 7 Days*, *Older*).
  - Instant live thread search, inline renaming, and thread deletion with cascade cleanup.
- **Hierarchical `.env` Secret Loader**: Zero-leak environment discovery and prioritization (`.env`, `~/.syntrak/.env`, system variables).
- **Web App Favicons & Manifest**: Complete icon suite (16x16, 32x32, 180x180, 192x192, 512x512) and `site.webmanifest`.
- **Keep-Alive GitHub Action**: Added workflow to keep Render demo instances active 24/7.

### Changed
- Replaced project references from legacy names to `syntrak`.
- Enhanced `SyntrakConfig` to dynamically resolve workspace roots.

---

## [0.1.0] - 2026-08-14

### Added
- **Initial Public Release of Syntrak**.
- **ReAct Orchestration Engine**: Iterative reasoning and action cycle with token-bounded steps and real-time streaming parser.
- **LiteLLM Gateway**: Multi-provider support interfacing uniformly with Ollama, NVIDIA NIM, OpenAI, Anthropic Claude, Google Gemini, Groq, OpenRouter, and vLLM.
- **Terminal REPL**: Monospace command-line interface built on `prompt_toolkit` and `rich` with slash commands (`/review`, `/diff`, `/undo`, `/model`, `/clear`).
- **Neovim Monospace Web Console (`syntrak.nvim`)**:
  - Bufferline navigation tabs (`agent.buf`, `review.diff`, `config.lua`).
  - 5 classic color schemes: Gruvbox Dark, Nord, Tokyo Night, Monokai Pro, and Solarized Dark.
  - Live Server-Sent Events (SSE) streaming API (`/api/chat/stream`).
- **Precision Tool Execution Engine**:
  - `replace_in_file`: Safe targeted substring chunk editing without full-file hallucinations.
  - `read_file`, `write_file`, `list_dir`, `search_files`.
  - `git_diff` & `git_status`: Automated repository state inspection.
  - `create_snapshot` & `rollback_snapshot`: Instant safe rollback (`/undo`).
  - `review_ops`: Automated PR and working tree diff inspection.
- **Packaging**: PyPI packaging configuration with `setuptools`, CLI entrypoint `syntrak`, and cloud deployment blueprints (`render.yaml`).
