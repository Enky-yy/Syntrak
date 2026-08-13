"""Conversation history and token-aware memory compaction for CampusCLI."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def estimate_tokens(text: str) -> int:
    """Fast rule-of-thumb token estimator (approx 4 chars per token)."""
    return max(1, len(text) // 4)


def estimate_messages_tokens(messages: List[Dict[str, Any]]) -> int:
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += estimate_tokens(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and "text" in part:
                    total += estimate_tokens(part["text"])
        # Tool call arguments
        if "tool_calls" in msg and msg["tool_calls"]:
            for tc in msg["tool_calls"]:
                func = tc.get("function", {})
                total += estimate_tokens(func.get("name", "") + func.get("arguments", ""))
    return total


class MemoryManager:
    """Manages chat messages and automatically compacts history to stay within model limits."""

    def __init__(self, context_limit: int = 32768, target_ratio: float = 0.7):
        self.context_limit = context_limit
        self.max_tokens = int(context_limit * target_ratio)
        self.messages: List[Dict[str, Any]] = []

    def add_message(self, role: str, content: Any, **kwargs):
        msg: Dict[str, Any] = {"role": role, "content": content}
        msg.update(kwargs)
        self.messages.append(msg)
        self.compact_if_needed()

    def get_messages(self) -> List[Dict[str, Any]]:
        return list(self.messages)

    def clear(self):
        self.messages.clear()

    def compact_if_needed(self) -> bool:
        """Compact older history if total tokens exceed max_tokens."""
        total_tokens = estimate_messages_tokens(self.messages)
        if total_tokens <= self.max_tokens or len(self.messages) <= 4:
            return False

        # Preserve system prompt (message 0 if system) and last 4 recent messages
        system_msg = None
        start_idx = 0
        if self.messages and self.messages[0].get("role") == "system":
            system_msg = self.messages[0]
            start_idx = 1

        recent_window = 4
        if len(self.messages) - start_idx <= recent_window:
            return False

        messages_to_compress = self.messages[start_idx:-recent_window]
        recent_messages = self.messages[-recent_window:]

        summary_snippets = []
        for m in messages_to_compress:
            role = m.get("role", "unknown")
            content = str(m.get("content", ""))[:120]
            summary_snippets.append(f"- {role}: {content}...")

        summary_content = (
            f"[Previous conversation summary compacted ({len(messages_to_compress)} messages)]:\n"
            + "\n".join(summary_snippets)
        )

        new_history = []
        if system_msg:
            new_history.append(system_msg)

        new_history.append({"role": "system", "content": summary_content})
        new_history.extend(recent_messages)

        self.messages = new_history
        return True
