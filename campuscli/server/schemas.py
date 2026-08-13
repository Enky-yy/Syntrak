"""Pydantic schemas for the CampusCLI Web API server."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(..., description="User prompt or instruction")
    custom_instructions: Optional[str] = None


class SwitchModelRequest(BaseModel):
    model: str = Field(..., description="New model name (e.g. ollama/qwen2.5-coder:32b)")
    api_base: Optional[str] = None
    api_key: Optional[str] = None


class SessionInfoResponse(BaseModel):
    model: str
    api_base: Optional[str]
    workspace_root: str
    git_status: str
    max_steps: int


class ReviewRequest(BaseModel):
    staged_only: bool = False
    target_branch: Optional[str] = None
