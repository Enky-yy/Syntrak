"""Tests for Agent ReAct loop with Mock LLM."""

import pytest
from typing import Any, AsyncGenerator, Dict, List, Optional
from campuscli.core.agent import AgentRunner
from campuscli.core.events import DoneEvent, TokenStreamEvent, ToolResultEvent, ToolStartEvent
from campuscli.core.memory import MemoryManager
from campuscli.llm.base import BaseLLMClient, LLMResponseChunk
from campuscli.tools.base import ToolRegistry


class MockLLMClient(BaseLLMClient):
    """Mock LLM that calls read_file first and then answers."""

    def __init__(self):
        self.call_count = 0

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096
    ) -> AsyncGenerator[LLMResponseChunk, None]:
        self.call_count += 1
        if self.call_count == 1:
            # First turn: trigger a tool call
            yield LLMResponseChunk(delta_text="Let me inspect the file.\n")
            yield LLMResponseChunk(
                is_done=True,
                tool_calls=[{
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "mock_tool",
                        "arguments": '{"param": "test_val"}'
                    }
                }],
                finish_reason="tool_calls"
            )
        else:
            # Second turn: complete
            yield LLMResponseChunk(delta_text="Inspection complete! Everything looks great.")
            yield LLMResponseChunk(is_done=True, tool_calls=[], finish_reason="stop")


@pytest.mark.asyncio
async def test_agent_react_loop():
    registry = ToolRegistry()

    @registry.register(name="mock_tool", description="Mock tool for testing")
    def mock_tool(param: str) -> str:
        return f"Result for {param}"

    mem = MemoryManager()
    mock_llm = MockLLMClient()
    agent = AgentRunner(llm_client=mock_llm, tool_registry=registry, memory_manager=mem)

    events = []
    async for ev in agent.run(user_query="Please test the mock tool."):
        events.append(ev)

    event_types = [e.event_type.value for e in events]
    assert "agent_status" in event_types
    assert "token_stream" in event_types
    assert "tool_start" in event_types
    assert "tool_result" in event_types
    assert "done" in event_types
