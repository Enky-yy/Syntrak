"""FastAPI server exposing CampusCLI core engine for Web frontends."""

import json
from pathlib import Path
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from campuscli.config import CampusConfig
from campuscli.core.session import SessionManager
from campuscli.server.schemas import (
    ChatRequest,
    ReviewRequest,
    SessionInfoResponse,
    SwitchModelRequest,
)
from campuscli.tools.git_ops import git_diff, git_status


def create_app(config: CampusConfig = None) -> FastAPI:
    """Create and configure FastAPI application for Web UI."""
    app = FastAPI(
        title="CampusCLI API & Web UI",
        description="REST & SSE Streaming API and Web Dashboard for CampusCLI",
        version="0.1.0"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    session = SessionManager(config=config)
    static_dir = Path(__file__).parent / "static"

    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @app.get("/")
        async def serve_index():
            """Serve CampusCLI Web Dashboard."""
            return FileResponse(str(static_dir / "index.html"))

    @app.get("/api/session/status", response_model=SessionInfoResponse)
    async def get_session_status():
        """Retrieve current session metadata and workspace info."""
        return SessionInfoResponse(
            model=session.config.llm.model,
            api_base=session.config.llm.api_base,
            workspace_root=session.config.workspace_root,
            git_status=git_status(),
            max_steps=session.config.max_agent_steps
        )

    @app.post("/api/model")
    async def switch_model(req: SwitchModelRequest):
        """Switch active LLM model/endpoint."""
        session.set_model(model_name=req.model, api_base=req.api_base, api_key=req.api_key)
        return {"status": "success", "active_model": session.config.llm.model}

    @app.get("/api/diff")
    async def get_diff(staged: bool = False, target_branch: str = None):
        """Get git diff for web visualization."""
        diff_text = git_diff(staged=staged, target_branch=target_branch)
        return {"diff": diff_text}

    @app.post("/api/chat/stream")
    async def chat_stream(req: ChatRequest):
        """Stream agent events as Server-Sent Events (SSE) to Web UI."""
        async def event_generator() -> AsyncGenerator[str, None]:
            try:
                async for event in session.execute_query(
                    query=req.query,
                    custom_instructions=req.custom_instructions
                ):
                    event_data = json.dumps(event.model_dump())
                    yield f"data: {event_data}\n\n"
            except Exception as e:
                err_data = json.dumps({"event_type": "error", "message": str(e)})
                yield f"data: {err_data}\n\n"

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
