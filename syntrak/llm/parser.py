"""Parser for extracting structured tool calls from raw LLM text responses."""

import json
import re
from typing import Any, Dict, List, Optional, Tuple


def parse_xml_tool_calls(text: str) -> Tuple[str, List[Dict[str, Any]]]:
    """Parse <tool_call><name>...</name><arguments>...</arguments></tool_call> tags.
    
    Returns:
        clean_text: Text with tool call tags stripped out.
        tool_calls: List of parsed tool call dicts in standard format:
                    [{'id': 'call_1', 'function': {'name': '...', 'arguments': '{...}'}}]
    """
    pattern = re.compile(
        r"<tool_call>\s*<name>(.*?)</name>\s*<arguments>(.*?)</arguments>\s*</tool_call>",
        re.DOTALL | re.IGNORECASE
    )

    tool_calls: List[Dict[str, Any]] = []
    call_idx = 0

    def _replacer(match: re.Match) -> str:
        nonlocal call_idx
        call_idx += 1
        name = match.group(1).strip()
        args_raw = match.group(2).strip()

        # Validate JSON or parse key-value
        try:
            parsed_args = json.loads(args_raw)
        except Exception:
            parsed_args = {"raw_args": args_raw}

        tool_calls.append({
            "id": f"call_xml_{call_idx}",
            "type": "function",
            "function": {
                "name": name,
                "arguments": json.dumps(parsed_args)
            }
        })
        return ""

    clean_text = pattern.sub(_replacer, text).strip()
    return clean_text, tool_calls


def parse_markdown_tool_calls(text: str) -> Tuple[str, List[Dict[str, Any]]]:
    """Parse ```tool_call / ```json tool calling blocks when XML tags aren't used."""
    pattern = re.compile(
        r"^[ \t]*```(?:tool_call|json:tool|json)?\s*\n(.*?)\n[ \t]*```",
        re.DOTALL | re.MULTILINE | re.IGNORECASE
    )

    tool_calls: List[Dict[str, Any]] = []
    call_idx = 0

    def _replacer(match: re.Match) -> str:
        nonlocal call_idx
        block = match.group(1).strip()
        try:
            data = json.loads(block)
            if isinstance(data, dict):
                name = data.get("tool") or data.get("name") or data.get("action")
                args = data.get("parameters") or data.get("arguments") or data.get("args") or {}
                if name:
                    call_idx += 1
                    tool_calls.append({
                        "id": f"call_md_{call_idx}",
                        "type": "function",
                        "function": {
                            "name": name,
                            "arguments": json.dumps(args) if isinstance(args, dict) else str(args)
                        }
                    })
                    return ""
        except Exception:
            pass
        return match.group(0)

    clean_text = pattern.sub(_replacer, text).strip()
    return clean_text, tool_calls
