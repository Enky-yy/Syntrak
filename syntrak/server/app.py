"""FastAPI server exposing Syntrak core engine, Google Auth, and Chat History."""

import json
import os
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional
from fastapi import Depends, FastAPI, HTTPException, Response
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
    verify_google_credential,
)
from syntrak.server.db import Database, default_db
from syntrak.server.schemas import (
    AuthResponse,
    ChatRequest,
    ConversationDetail,
    ConversationSummary,
    CreateConversationRequest,
    GoogleAuthRequest,
    ReviewRequest,
    SessionInfoResponse,
    SwitchModelRequest,
    UpdateConversationRequest,
    UserResponse,
)
from syntrak.tools.git_ops import git_diff, git_status


def create_app(config: SyntrakConfig = None, db: Database = None) -> FastAPI:
    """Create and configure FastAPI application for Web UI."""
    app = FastAPI(
        title="Syntrak API & Web UI",
        description="REST & SSE Streaming API, Google Authentication, and Chat History for Syntrak",
        version="0.1.0"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    database = db or default_db
    session = SessionManager(config=config)
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
            httponly=False,
            max_age=86400 * 30,
            samesite="lax"
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
    async def auth_logout(response: Response):
        """Log out user and clear session cookie."""
        response.delete_cookie(key="syntrak_token", path="/")
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
    async def list_conversations(user: Dict = Depends(get_current_user)):
        """List all conversation threads for the current user."""
        convs = database.get_conversations(user_id=user["id"])
        return [
            ConversationSummary(
                id=c["id"],
                user_id=c["user_id"],
                title=c["title"],
                message_count=c.get("message_count", 0),
                created_at=c["created_at"],
                updated_at=c["updated_at"]
            )
            for c in convs
        ]

    @app.post("/api/conversations", response_model=ConversationSummary)
    async def create_conversation(req: CreateConversationRequest = None, user: Dict = Depends(get_current_user)):
        """Create a new conversation thread."""
        title = req.title if req and req.title else "New Chat"
        conv = database.create_conversation(user_id=user["id"], title=title)
        return ConversationSummary(
            id=conv["id"],
            user_id=conv["user_id"],
            title=conv["title"],
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
        return SessionInfoResponse(
            model=session.config.llm.model,
            api_base=session.config.llm.api_base,
            workspace_root=session.config.workspace_root,
            git_status=git_status(),
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
    async def switch_model(req: SwitchModelRequest):
        """Switch active LLM model/endpoint or update google_client_id."""
        session.set_model(model_name=req.model, api_base=req.api_base, api_key=req.api_key)
        if req.google_client_id is not None:
            session.config.google_client_id = req.google_client_id.strip() or None
        return {"status": "success", "active_model": session.config.llm.model, "google_client_id": session.config.google_client_id}

    @app.get("/api/diff")
    async def get_diff(staged: bool = False, target_branch: str = None):
        """Get git diff for web visualization."""
        diff_text = git_diff(staged=staged, target_branch=target_branch)
        return {"diff": diff_text}

    @app.post("/api/chat/stream")
    async def chat_stream(req: ChatRequest, user: Dict = Depends(get_current_user)):
        """Stream agent events as SSE and persist messages to active conversation."""
        # Ensure or create active conversation
        conv_id = req.conversation_id
        if not conv_id:
            first_title = req.query.strip().split("\n")[0][:35] or "New Chat"
            new_conv = database.create_conversation(user_id=user["id"], title=first_title)
            conv_id = new_conv["id"]
        else:
            # If current title is "New Chat", auto-update to query title
            curr = database.get_conversation(conv_id, user_id=user["id"])
            if curr and curr["title"] == "New Chat":
                new_title = req.query.strip().split("\n")[0][:35]
                database.update_conversation_title(conv_id, new_title, user_id=user["id"])

        # Persist user message to DB
        database.add_message(
            conversation_id=conv_id,
            role="user",
            content=req.query
        )

        async def event_generator() -> AsyncGenerator[str, None]:
            accumulated_assistant = ""
            events_log = []

            # Send conversation_id envelope first
            conv_init = json.dumps({"event_type": "conversation_init", "conversation_id": conv_id})
            yield f"data: {conv_init}\n\n"

            try:
                async for event in session.execute_query(
                    query=req.query,
                    custom_instructions=req.custom_instructions
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
    async def undo_change():
        """Undo last agent action via git snapshot."""
        res = session.undo_last_change()
        return {"result": res}

    @app.post("/api/clear")
    async def clear_memory():
        """Reset conversation memory."""
        session.memory.clear()
        return {"status": "success"}

    return app


app = create_app()
