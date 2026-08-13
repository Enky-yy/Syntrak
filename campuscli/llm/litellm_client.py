"""LiteLLM integration client supporting Open Source and commercial LLM providers."""

import os
from typing import Any, AsyncGenerator, Dict, List, Optional
import litellm
from campuscli.config import LLMConfig
from campuscli.llm.base import BaseLLMClient, LLMResponseChunk
from campuscli.llm.parser import parse_markdown_tool_calls, parse_xml_tool_calls


# Disable verbose litellm logs
litellm.suppress_debug_info = True


class LiteLLMClient(BaseLLMClient):
    """Unified client for Ollama, vLLM, OpenAI, and open-source models using LiteLLM."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.model = config.model
        self.api_base = config.api_base
        self.api_key = config.api_key or os.getenv("OPENAI_API_KEY")

        # Automatically adjust Ollama model prefix if needed
        if "ollama" in self.model.lower() and not self.api_base:
            self.api_base = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[LLMResponseChunk, None]:
        """Stream response chunks from LiteLLM, handling tool calls and reasoning deltas."""
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens if max_tokens is not None else self.config.max_tokens

        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "temperature": temp,
            "max_tokens": tokens,
        }

        if self.api_base:
            kwargs["api_base"] = self.api_base
        if self.api_key:
            kwargs["api_key"] = self.api_key

        # If native tool calling is enabled and tools are passed
        if tools and not self.config.force_xml_tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        accumulated_text = ""
        tool_call_collector: Dict[int, Dict[str, Any]] = {}

        try:
            response = await litellm.acompletion(**kwargs)
            async for chunk in response:
                delta_text = ""
                delta_thought = ""
                choice = chunk.choices[0] if chunk.choices else None

                if choice and choice.delta:
                    delta = choice.delta

                    # Reasoning/thought content from models like DeepSeek-R1 / QwQ
                    if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                        delta_thought = delta.reasoning_content
                    elif hasattr(delta, "thought") and delta.thought:
                        delta_thought = delta.thought

                    if delta.content:
                        content_str = delta.content
                        accumulated_text += content_str
                        # Suppress inline think / thought tags
                        if not ("<think>" in content_str or "</think>" in content_str or "<thought>" in content_str or "</thought>" in content_str):
                            delta_text = content_str

                    # Native tool calls accumulation
                    if hasattr(delta, "tool_calls") and delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index if hasattr(tc, "index") else 0
                            if idx not in tool_call_collector:
                                tool_call_collector[idx] = {
                                    "id": getattr(tc, "id", f"call_{idx}") or f"call_{idx}",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""}
                                }
                            if hasattr(tc, "function") and tc.function:
                                if getattr(tc.function, "name", None):
                                    tool_call_collector[idx]["function"]["name"] += tc.function.name
                                if getattr(tc.function, "arguments", None):
                                    tool_call_collector[idx]["function"]["arguments"] += tc.function.arguments

                yield LLMResponseChunk(
                    delta_text=delta_text,
                    delta_thought=delta_thought,
                    is_done=False
                )

        except Exception as e:
            # Provide actionable diagnostic message for connection / model failures
            err_msg = str(e)
            if "ConnectionRefused" in err_msg or "Failed to establish a new connection" in err_msg:
                if "11434" in (self.api_base or ""):
                    err_msg = (
                        f"Could not connect to Ollama at {self.api_base}. "
                        "Is Ollama running? (Start it with `ollama serve` and pull your model)."
                    )
            raise RuntimeError(f"LLM Error ({self.model}): {err_msg}") from e

        # Finalize and parse tool calls if any
        final_tool_calls: List[Dict[str, Any]] = list(tool_call_collector.values())

        # If no native tool calls were caught, check for XML/Markdown tool blocks in accumulated text
        if not final_tool_calls and accumulated_text:
            clean_xml, xml_calls = parse_xml_tool_calls(accumulated_text)
            if xml_calls:
                final_tool_calls.extend(xml_calls)
            else:
                clean_md, md_calls = parse_markdown_tool_calls(accumulated_text)
                if md_calls:
                    final_tool_calls.extend(md_calls)

        yield LLMResponseChunk(
            is_done=True,
            tool_calls=final_tool_calls,
            finish_reason="stop" if not final_tool_calls else "tool_calls"
        )
