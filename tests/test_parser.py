"""Tests for tool call extraction and parsing."""

from syntrak.llm.parser import parse_markdown_tool_calls, parse_xml_tool_calls


def test_parse_xml_tool_calls():
    sample_text = """
    I will now read the file to understand its content.
    <tool_call>
    <name>read_file</name>
    <arguments>
    {"file_path": "main.py"}
    </arguments>
    </tool_call>
    Let's check the result.
    """
    clean_text, tool_calls = parse_xml_tool_calls(sample_text)

    assert "<tool_call>" not in clean_text
    assert len(tool_calls) == 1
    assert tool_calls[0]["function"]["name"] == "read_file"
    assert '"file_path": "main.py"' in tool_calls[0]["function"]["arguments"]


def test_parse_markdown_tool_calls():
    sample_text = """
    ```tool_call
    {
      "tool": "git_status",
      "arguments": {}
    }
    ```
    """
    clean_text, tool_calls = parse_markdown_tool_calls(sample_text)

    assert len(tool_calls) == 1
    assert tool_calls[0]["function"]["name"] == "git_status"
