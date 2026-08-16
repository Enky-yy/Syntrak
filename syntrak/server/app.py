"""FastAPI server exposing Syntrak core engine, Google Auth, and Chat History."""

from collections import defaultdict
import json
import os
from pathlib import Path
import re
import subprocess
import time
from typing import AsyncGenerator, Dict, List, Optional
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from syntrak.config import SyntrakConfig
from syntrak.core.events import (
    AgentStatusEvent,
    DoneEvent,
    ErrorEvent,
    ThoughtStreamEvent,
    TokenStreamEvent,
    ToolResultEvent,
    ToolStartEvent,
)
from syntrak.core.session import SessionManager
from syntrak.server.auth import (
    create_jwt_token,
    get_current_user,
    revoke_jwt_token,
    verify_google_credential,
)
from syntrak.server.db import Database, default_db
from syntrak.server.schemas import (
    AuthResponse,
    AuthorizeRepoRequest,
    ChatRequest,
    ConnectGithubRepoRequest,
    ConnectGithubRepoResponse,
    ConversationDetail,
    ConversationSummary,
    CreateConversationRequest,
    GoogleAuthRequest,
    RepoInfoResponse,
    ReviewRequest,
    SessionInfoResponse,
    SwitchModelRequest,
    UpdateConversationRequest,
    UserResponse,
)
from syntrak.tools.git_ops import (
    git_diff,
    git_get_branch,
    git_get_remote_url,
    git_status,
)

BLOCKED_SSRF_HOSTS = [
    "169.254.169.254",
    "metadata.google.internal",
    "metadata.google",
    "100.100.100.200",
]


def _validate_api_base_ssrf(api_base: Optional[str]) -> None:
    """Validate that custom API base URLs do not target internal cloud metadata endpoints."""
    if not api_base or not api_base.strip():
        return
    cleaned = api_base.strip().lower()
    for blocked in BLOCKED_SSRF_HOSTS:
        if blocked in cleaned:
            raise HTTPException(
                status_code=400,
                detail=f"Security Violation: Target host '{blocked}' is blocked by SSRF protection policy."
            )


# In-memory sliding window rate limiter
_request_rate_log: Dict[str, List[float]] = defaultdict(list)


def _check_rate_limit(client_id: str, max_requests: int = 60, window_seconds: int = 60) -> None:
    """Check and record client request timestamps for rate limiting."""
    now = time.time()
    timestamps = _request_rate_log[client_id]
    # Prune timestamps outside window
    _request_rate_log[client_id] = [t for t in timestamps if now - t < window_seconds]
    if len(_request_rate_log[client_id]) >= max_requests:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({max_requests} requests per {window_seconds}s). Please slow down."
        )
    _request_rate_log[client_id].append(now)


def create_app(config: SyntrakConfig = None, db: Database = None) -> FastAPI:
    """Create and configure FastAPI application for Web UI."""
    app = FastAPI(
        title="Syntrak API & Web UI",
        description="REST & SSE Streaming API, Google Authentication, and Chat History for Syntrak",
        version="0.2.0"
    )

    # Security Headers Middleware
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self' 'unsafe-inline' 'unsafe-eval' https://accounts.google.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com https://fonts.gstatic.com; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://accounts.google.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://fonts.googleapis.com https://cdn.jsdelivr.net; "
            "font-src 'self' data: https://cdnjs.cloudflare.com https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self' https://accounts.google.com https://oauth2.googleapis.com ws: wss:; "
            "frame-src https://accounts.google.com;"
        )
        return response

    # Maximum Request Body Size Middleware (5 MB limit)
    @app.middleware("http")
    async def limit_request_size(request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > 5 * 1024 * 1024:
                    return Response(content="Request payload too large (max 5 MB)", status_code=413)
            except ValueError:
                pass
        return await call_next(request)

    allowed_origins_env = os.getenv("SYNTRAK_ALLOWED_ORIGINS", "")
    if allowed_origins_env:
        allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
    else:
        allowed_origins = [
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:9000",
            "http://127.0.0.1:9000",
            "https://syntrak.harsh-shah.me"
        ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    database = db or default_db
    session = SessionManager(config=config)
    session.has_connected_repo = False
    os.environ.pop("SYNTRAK_WORKSPACE_ROOT", None)
    static_dir = Path(__file__).parent / "static"

    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @app.get("/")
        async def serve_index():
            """Serve Syntrak Web Dashboard."""
            return FileResponse(str(static_dir / "index.html"))

    # Authentication Endpoints
    @app.post("/api/auth/google", response_model=AuthResponse)
    async def auth_google(req: GoogleAuthRequest, response: Response):
        """Authenticate user using Google Identity Services ID token."""
        user_info = await verify_google_credential(req.credential)
        user_record = database.upsert_user(
            user_id=user_info["id"],
            email=user_info["email"],
            name=user_info.get("name"),
            picture=user_info.get("picture")
        )
        token = create_jwt_token(user_record)
        response.set_cookie(
            key="syntrak_token",
            value=token,
            httponly=True,
            max_age=86400 * 30,
            samesite="lax",
            secure=bool(os.getenv("PRODUCTION", False))
        )
        return AuthResponse(
            token=token,
            user=UserResponse(
                id=user_record["id"],
                email=user_record["email"],
                name=user_record.get("name"),
                picture=user_record.get("picture")
            )
        )

    @app.post("/api/auth/logout")
    async def auth_logout(request: Request, response: Response, authorization: Optional[str] = Header(None)):
        """Log out user, revoke session token, and clear session cookie."""
        token = None
        if authorization and authorization.startswith("Bearer "):
            token = authorization.split("Bearer ", 1)[1].strip()
        elif "syntrak_token" in request.cookies:
            token = request.cookies.get("syntrak_token")
        if token:
            revoke_jwt_token(token)
        response.delete_cookie(key="syntrak_token", path="/", httponly=True)
        return {"status": "success", "message": "Logged out successfully"}

    @app.get("/api/auth/me", response_model=UserResponse)
    async def get_me(user: Dict = Depends(get_current_user)):
        """Get profile of current logged-in user."""
        return UserResponse(
            id=user["id"],
            email=user["email"],
            name=user.get("name"),
            picture=user.get("picture")
        )

    # Conversation History Endpoints
    @app.get("/api/conversations", response_model=List[ConversationSummary])
    async def list_conversations(mode: Optional[str] = None, user: Dict = Depends(get_current_user)):
        """List all conversation threads for the current user, optionally filtered by mode."""
        convs = database.get_conversations(user_id=user["id"], mode=mode)
        return [
            ConversationSummary(
                id=c["id"],
                user_id=c["user_id"],
                title=c["title"],
                mode=c.get("mode", "chat") or "chat",
                message_count=c.get("message_count", 0),
                created_at=c["created_at"],
                updated_at=c["updated_at"]
            )
            for c in convs
        ]

    @app.post("/api/conversations", response_model=ConversationSummary)
    async def create_conversation(req: CreateConversationRequest = None, user: Dict = Depends(get_current_user)):
        """Create a new conversation thread."""
        c_mode = req.mode if req and req.mode else "chat"
        title = req.title if req and req.title else ("New Agent Session" if c_mode == "agent" else "New Chat")
        conv = database.create_conversation(user_id=user["id"], title=title, mode=c_mode)
        return ConversationSummary(
            id=conv["id"],
            user_id=conv["user_id"],
            title=conv["title"],
            mode=conv.get("mode", "chat") or "chat",
            message_count=0,
            created_at=conv["created_at"],
            updated_at=conv["updated_at"]
        )

    @app.get("/api/conversations/{conv_id}", response_model=ConversationDetail)
    async def get_conversation(conv_id: str, user: Dict = Depends(get_current_user)):
        """Retrieve conversation details and historical messages."""
        conv = database.get_conversation(conv_id, user_id=user["id"])
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

        messages = database.get_messages(conv_id)
        return ConversationDetail(
            id=conv["id"],
            user_id=conv["user_id"],
            title=conv["title"],
            mode=conv.get("mode", "chat") or "chat",
            created_at=conv["created_at"],
            updated_at=conv["updated_at"],
            messages=messages
        )

    @app.patch("/api/conversations/{conv_id}", response_model=ConversationSummary)
    async def update_conversation(conv_id: str, req: UpdateConversationRequest, user: Dict = Depends(get_current_user)):
        """Rename a conversation thread."""
        success = database.update_conversation_title(conv_id, title=req.title, user_id=user["id"])
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")

        conv = database.get_conversation(conv_id, user_id=user["id"])
        return ConversationSummary(
            id=conv["id"],
            user_id=conv["user_id"],
            title=conv["title"],
            mode=conv.get("mode", "chat") or "chat",
            created_at=conv["created_at"],
            updated_at=conv["updated_at"]
        )

    @app.delete("/api/conversations/{conv_id}")
    async def delete_conversation(conv_id: str, user: Dict = Depends(get_current_user)):
        """Delete a conversation thread and its messages."""
        success = database.delete_conversation(conv_id, user_id=user["id"])
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return {"status": "success", "deleted_id": conv_id}

    # Core System Endpoints
    @app.get("/api/session/status", response_model=SessionInfoResponse)
    async def get_session_status(user: Dict = Depends(get_current_user)):
        """Retrieve current session metadata, workspace info, and active user."""
        has_connected = getattr(session, "has_connected_repo", False)
        connected_name = Path(session.config.workspace_root).name if has_connected else None
        ws_root = session.config.workspace_root if has_connected else None
        git_stat = git_status() if has_connected else "No repository connected"

        return SessionInfoResponse(
            model=session.config.llm.model,
            api_base=session.config.llm.api_base,
            workspace_root=ws_root,
            has_connected_repo=has_connected,
            connected_repo_name=connected_name,
            git_status=git_stat,
            max_steps=session.config.max_agent_steps,
            google_client_id=session.config.google_client_id or os.getenv("GOOGLE_CLIENT_ID"),
            user=UserResponse(
                id=user["id"],
                email=user["email"],
                name=user.get("name"),
                picture=user.get("picture")
            )
        )


    @app.post("/api/model")
    async def switch_model(req: SwitchModelRequest, user: Dict = Depends(get_current_user)):
        """Switch active LLM model/endpoint or update google_client_id with SSRF check."""
        _validate_api_base_ssrf(req.api_base)
        session.set_model(model_name=req.model, api_base=req.api_base, api_key=req.api_key)
        if req.google_client_id is not None:
            session.config.google_client_id = req.google_client_id.strip() or None
        return {"status": "success", "active_model": session.config.llm.model, "google_client_id": session.config.google_client_id}

    @app.get("/api/diff")
    async def get_diff(staged: bool = False, target_branch: Optional[str] = None, user: Dict = Depends(get_current_user)):
        """Get git diff for web visualization with branch input sanitization."""
        cleaned_branch = None
        if target_branch:
            cleaned_branch = target_branch.strip()
            if cleaned_branch.startswith("-") or not re.match(r"^[a-zA-Z0-9_\-\./]+$", cleaned_branch):
                raise HTTPException(status_code=400, detail="Invalid target branch name format.")
        diff_text = git_diff(staged=staged, target_branch=cleaned_branch)
        return {"diff": diff_text}

    @app.get("/api/repo/info", response_model=RepoInfoResponse)
    async def get_repo_info(user: Dict = Depends(get_current_user)):
        """Retrieve workspace repository and git remote information."""
        ws_root = session.config.workspace_root
        ws_path = Path(ws_root).resolve()
        repo_name = ws_path.name
        remote_url = git_get_remote_url(cwd=str(ws_path))
        branch = git_get_branch(cwd=str(ws_path))
        is_git = (ws_path / ".git").exists()
        return RepoInfoResponse(
            workspace_root=str(ws_path),
            repo_name=repo_name,
            git_remote=remote_url,
            branch=branch,
            is_git_repo=is_git
        )

    @app.post("/api/repo/authorize")
    async def authorize_repo(req: AuthorizeRepoRequest, user: Dict = Depends(get_current_user)):
        """Authorize repository access for Agent Mode without mutating global process environment."""
        if req.github_token:
            session.github_token = req.github_token.strip()
        elif not req.grant:
            session.github_token = None
        return {
            "status": "success",
            "granted": req.grant,
            "message": "Repository access authorized for Agent Mode." if req.grant else "Repository access revoked."
        }

    @app.post("/api/repo/connect", response_model=ConnectGithubRepoResponse)
    async def connect_repo(req: ConnectGithubRepoRequest, user: Dict = Depends(get_current_user)):
        """Connect and clone/checkout user's GitHub repository for Agent Mode."""
        _check_rate_limit(client_id=f"repo_{user['id']}", max_requests=10, window_seconds=60)
        if not req.repo_url:
            raise HTTPException(status_code=400, detail="Please provide a GitHub repository URL or owner/repo (e.g. 'username/repo-name').")

        raw_url = req.repo_url.strip()
        if raw_url.startswith("-"):
            raise HTTPException(status_code=400, detail="Invalid repository URL format.")

        branch = req.branch.strip() if req.branch else "main"
        if branch.startswith("-") or not re.match(r"^[a-zA-Z0-9_\-\./]+$", branch):
            raise HTTPException(status_code=400, detail="Invalid branch name format.")

        cleaned_url = raw_url
        if not cleaned_url.startswith("http://") and not cleaned_url.startswith("https://") and not cleaned_url.startswith("git@"):
            cleaned_url = f"https://github.com/{cleaned_url.strip('/')}"

        slug_clean = cleaned_url.rstrip("/").removesuffix(".git")
        slug_parts = slug_clean.split("/")[-2:]
        raw_slug = "_".join(slug_parts) if len(slug_parts) == 2 else slug_clean.split("/")[-1]
        slug_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", raw_slug)
        repo_display_name = "/".join(slug_parts) if len(slug_parts) == 2 else slug_name

        workspaces_dir = Path.home() / ".syntrak" / "workspaces"
        workspaces_dir.mkdir(parents=True, exist_ok=True)
        target_repo_dir = (workspaces_dir / slug_name).resolve()

        # Prevent directory traversal outside ~/.syntrak/workspaces
        if not str(target_repo_dir).startswith(str(workspaces_dir.resolve())):
            raise HTTPException(status_code=400, detail="Invalid workspace path target.")

        token = req.github_token.strip() if req.github_token else getattr(session, "github_token", None) or os.getenv("GITHUB_TOKEN")
        clone_url = cleaned_url
        if token and clone_url.startswith("https://github.com/"):
            clone_url = clone_url.replace("https://github.com/", f"https://{token}@github.com/")

        git_env = os.environ.copy()
        if token:
            git_env["GITHUB_TOKEN"] = token

        if target_repo_dir.exists() and (target_repo_dir / ".git").exists():
            try:
                subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "fetch"], cwd=str(target_repo_dir), capture_output=True, text=True, check=False, env=git_env)
                subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "checkout", branch], cwd=str(target_repo_dir), capture_output=True, text=True, check=False, env=git_env)
            except Exception:
                pass
        else:
            target_repo_dir.mkdir(parents=True, exist_ok=True)
            clone_cmd = ["git", "-c", "core.hooksPath=/dev/null", "clone", "--depth", "50"]
            if branch:
                clone_cmd.extend(["-b", branch])
            clone_cmd.extend([clone_url, str(target_repo_dir)])
            res = subprocess.run(clone_cmd, capture_output=True, text=True, check=False, env=git_env)
            if res.returncode != 0:
                res_fallback = subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "clone", "--depth", "50", clone_url, str(target_repo_dir)], capture_output=True, text=True, check=False, env=git_env)
                if res_fallback.returncode != 0:
                    err_msg = res.stderr.strip() or res_fallback.stderr.strip()
                    if token:
                        err_msg = err_msg.replace(token, "***")
                    raise HTTPException(status_code=400, detail=f"Failed to clone GitHub repository: {err_msg}")

        # Sanitize remote origin URL so tokens are never persisted in .git/config
        subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "remote", "set-url", "origin", cleaned_url], cwd=str(target_repo_dir), capture_output=True, text=True, check=False, env=git_env)

        session.set_workspace(str(target_repo_dir))
        session.has_connected_repo = True
        if token:
            session.github_token = token
        actual_branch = git_get_branch(cwd=str(target_repo_dir)) or branch
        remote_origin = git_get_remote_url(cwd=str(target_repo_dir)) or raw_url

        return ConnectGithubRepoResponse(
            status="success",
            workspace_root=str(target_repo_dir),
            repo_name=repo_display_name,
            git_remote=remote_origin,
            branch=actual_branch,
            message=f"Successfully connected GitHub repository '{repo_display_name}' ({actual_branch})!"
        )


    @app.post("/api/chat/stream")
    async def chat_stream(req: ChatRequest, user: Dict = Depends(get_current_user)):
        """Stream agent events as SSE and persist messages to active conversation."""
        _check_rate_limit(client_id=f"stream_{user['id']}", max_requests=60, window_seconds=60)
        # Ensure or create active conversation
        conv_id = req.conversation_id
        if not conv_id:
            first_title = req.query.strip().split("\n")[0][:35] or ("New Agent Session" if req.mode == "agent" else "New Chat")
            new_conv = database.create_conversation(user_id=user["id"], title=first_title, mode=req.mode or "chat")
            conv_id = new_conv["id"]
        else:
            # Verify ownership of existing conversation thread to prevent IDOR
            curr = database.get_conversation(conv_id, user_id=user["id"])
            if not curr:
                raise HTTPException(status_code=404, detail="Conversation not found or unauthorized.")
            if curr["title"] in ("New Chat", "New Agent Session"):
                new_title = req.query.strip().split("\n")[0][:35]
                database.update_conversation_title(conv_id, new_title, user_id=user["id"])


        # Persist user message to DB
        database.add_message(
            conversation_id=conv_id,
            role="user",
            content=req.query
        )

        # Sync in-memory agent session with historical messages of THIS conversation thread
        prior_messages = database.get_messages(conv_id)
        if prior_messages and prior_messages[-1].get("role") == "user" and prior_messages[-1].get("content") == req.query:
            prior_messages = prior_messages[:-1]
        session.sync_conversation_history(prior_messages)

        async def event_generator() -> AsyncGenerator[str, None]:
            accumulated_assistant = ""
            events_log = []

            # Send conversation_id envelope first
            conv_init = json.dumps({"event_type": "conversation_init", "conversation_id": conv_id})
            yield f"data: {conv_init}\n\n"

            try:
                async for event in session.execute_query(
                    query=req.query,
                    custom_instructions=req.custom_instructions,
                    mode=req.mode,
                    repo_authorized=req.repo_authorized
                ):
                    event_dict = event.model_dump()
                    events_log.append(event_dict)

                    if isinstance(event, TokenStreamEvent):
                        accumulated_assistant += event.token

                    event_data = json.dumps(event_dict)
                    yield f"data: {event_data}\n\n"

                # Persist assistant response to DB
                database.add_message(
                    conversation_id=conv_id,
                    role="assistant",
                    content=accumulated_assistant or "(Completed)",
                    events=events_log
                )

            except Exception as e:
                err_dict = {"event_type": "error", "message": str(e)}
                events_log.append(err_dict)
                database.add_message(
                    conversation_id=conv_id,
                    role="assistant",
                    content=f"Error: {str(e)}",
                    events=events_log
                )
                yield f"data: {json.dumps(err_dict)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )

    @app.post("/api/undo")
    async def undo_change(user: Dict = Depends(get_current_user)):
        """Undo last agent action via git snapshot."""
        res = session.undo_last_change()
        return {"result": res}

    @app.post("/api/clear")
    async def clear_memory(user: Dict = Depends(get_current_user)):
        """Reset conversation memory."""
        session.memory.clear()
        return {"status": "success"}

    return app


app = create_app()
