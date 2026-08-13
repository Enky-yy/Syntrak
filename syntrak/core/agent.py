"""ReAct Agent Loop with streaming event architecture for Syntrak."""

import json
from typing import Any, AsyncGenerator, Dict, List, Optional
from syntrak.core.events import (
    AgentStatusEvent,
    BaseEvent,
    DoneEvent,
    ErrorEvent,
    ThoughtStreamEvent,
    TokenStreamEvent,
    ToolResultEvent,
    ToolStartEvent,
)
from syntrak.core.memory import MemoryManager
from syntrak.llm.base import BaseLLMClient
from syntrak.tools.base import ToolRegistry


class AgentRunner:
    """Orchestrates multi-turn ReAct loops between LLM and tool execution."""

    def __init__(
        self,
        llm_client: BaseLLMClient,
        tool_registry: ToolRegistry,
        memory_manager: MemoryManager,
        max_steps: int = 25
    ):
        self.llm = llm_client
        self.tools = tool_registry
        self.memory = memory_manager
        self.max_steps = max_steps

    async def run(
        self,
        user_query: str,
        system_prompt: Optional[str] = None
    ) -> AsyncGenerator[BaseEvent, None]:
        """Execute agent loop for a user query, yielding real-time stream events."""
        # Ensure system prompt is at index 0 if provided
        if system_prompt:
            current_msgs = self.memory.get_messages()
            if not current_msgs or current_msgs[0].get("role") != "system":
                self.memory.messages.insert(0, {"role": "system", "content": system_prompt})
            else:
                self.memory.messages[0]["content"] = system_prompt

        # Append user input
        self.memory.add_message(role="user", content=user_query)

        step = 0
        total_tokens = 0

        while step < self.max_steps:
            step += 1
            yield AgentStatusEvent(status=f"Step {step}/{self.max_steps}", step=step, max_steps=self.max_steps)

            messages = self.memory.get_messages()
            openai_tools = self.tools.to_openai_tools()

            accumulated_content = ""
            accumulated_thought = ""
            pending_tool_calls: List[Dict[str, Any]] = []

            try:
                async for chunk in self.llm.stream_chat(messages=messages, tools=openai_tools):
                    if chunk.delta_thought:
                        accumulated_thought += chunk.delta_thought
                        yield ThoughtStreamEvent(thought=chunk.delta_thought)

                    if chunk.delta_text:
                        accumulated_content += chunk.delta_text
                        yield TokenStreamEvent(token=chunk.delta_text)

                    if chunk.is_done:
                        pending_tool_calls = chunk.tool_calls

            except Exception as e:
                yield ErrorEvent(message=f"LLM generation failed: {str(e)}")
                break

            # Add assistant message to memory
            assistant_msg: Dict[str, Any] = {
                "role": "assistant",
                "content": accumulated_content or None
            }
            if pending_tool_calls:
                assistant_msg["tool_calls"] = pending_tool_calls

            self.memory.messages.append(assistant_msg)

            # If no tool calls requested, we have completed the user's turn
            if not pending_tool_calls:
                yield DoneEvent(finish_reason="stop")
                return

            # Execute pending tool calls
            for tc in pending_tool_calls:
                call_id = tc.get("id", "call_unknown")
                func_info = tc.get("function", {})
                tool_name = func_info.get("name", "")
                raw_args = func_info.get("arguments", "{}")

                # Parse arguments
                if isinstance(raw_args, str):
                    try:
                        args = json.loads(raw_args)
                    except Exception:
                        args = {"raw_input": raw_args}
                elif isinstance(raw_args, dict):
                    args = raw_args
                else:
                    args = {}

                yield ToolStartEvent(
                    tool_name=tool_name,
                    tool_id=call_id,
                    arguments=args
                )

                try:
                    tool_output = await self.tools.execute(tool_name, args)
                    success = True
                    error_msg = None
                except Exception as ex:
                    tool_output = f"Tool execution error: {str(ex)}"
                    success = False
                    error_msg = str(ex)

                yield ToolResultEvent(
                    tool_name=tool_name,
                    tool_id=call_id,
                    success=success,
                    output=tool_output,
                    error=error_msg
                )

                # Add tool result message to conversation memory
                self.memory.add_message(
                    role="tool",
                    content=str(tool_output),
                    tool_call_id=call_id,
                    name=tool_name
                )

        # Reached max steps
        yield DoneEvent(finish_reason="max_steps_reached")
