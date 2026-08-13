"""Tests for FastAPI Web API server endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient
from syntrak.server.app import create_app
from syntrak.config import SyntrakConfig


@pytest.mark.asyncio
async def test_session_status_and_model_switch():
    cfg = SyntrakConfig()
    app = create_app(config=cfg)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Test status
        res = await client.get("/api/session/status")
        assert res.status_code == 200
        data = res.json()
        assert "model" in data
        assert "workspace_root" in data

        # Test model switch
        switch_res = await client.post("/api/model", json={"model": "ollama/deepseek-coder-v2"})
        assert switch_res.status_code == 200
        assert switch_res.json()["active_model"] == "ollama/deepseek-coder-v2"

        # Test diff endpoint
        diff_res = await client.get("/api/diff")
        assert diff_res.status_code == 200
        assert "diff" in diff_res.json()
