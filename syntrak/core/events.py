"""Event definitions for Syntrak streaming and UI/Web updates."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import time


class EventType(str, Enum):
    TOKEN_STREAM = "token_stream"
    THOUGHT_STREAM = "thought_stream"
    TOOL_START = "tool_start"
    TOOL_RESULT = "tool_result"
    AGENT_STATUS = "agent_status"
    DIFF_PREVIEW = "diff_preview"
    REVIEW_RESULT = "review_result"
    ERROR = "error"
    DONE = "done"


class BaseEvent(BaseModel):
    event_type: EventType
    timestamp: float = Field(default_factory=time.time)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TokenStreamEvent(BaseEvent):
    event_type: EventType = EventType.TOKEN_STREAM
    token: str


class ThoughtStreamEvent(BaseEvent):
    event_type: EventType = EventType.THOUGHT_STREAM
    thought: str


class ToolStartEvent(BaseEvent):
    event_type: EventType = EventType.TOOL_START
    tool_name: str
    tool_id: str
    arguments: Dict[str, Any]


class ToolResultEvent(BaseEvent):
    event_type: EventType = EventType.TOOL_RESULT
    tool_name: str
    tool_id: str
    success: bool
    output: Any
    error: Optional[str] = None


class AgentStatusEvent(BaseEvent):
    event_type: EventType = EventType.AGENT_STATUS
    status: str
    step: int
    max_steps: int


class DiffPreviewEvent(BaseEvent):
    event_type: EventType = EventType.DIFF_PREVIEW
    file_path: str
    diff: str
    applied: bool = False


class ReviewResultEvent(BaseEvent):
    event_type: EventType = EventType.REVIEW_RESULT
    summary: str
    issues: List[Dict[str, Any]] = Field(default_factory=list)
    score: Optional[int] = None


class ErrorEvent(BaseEvent):
    event_type: EventType = EventType.ERROR
    message: str
    details: Optional[str] = None


class DoneEvent(BaseEvent):
    event_type: EventType = EventType.DONE
    total_tokens: Optional[int] = None
    finish_reason: Optional[str] = None
