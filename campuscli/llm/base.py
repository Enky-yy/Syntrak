"""Base interface for LLM clients in CampusCLI."""

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple
from pydantic import BaseModel


class LLMResponseChunk(BaseModel):
    delta_text: str = ""
    delta_thought: str = ""
    tool_calls: List[Dict[str, Any]] = []
    is_done: bool = False
    finish_reason: Optional[str] = None


class BaseLLMClient(ABC):
    """Abstract interface for interacting with LLMs."""

    @abstractmethod
    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096
    ) -> AsyncGenerator[LLMResponseChunk, None]:
        """Stream chat completion chunks from the LLM."""
        pass
