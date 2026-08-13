"""System prompt definitions and prompt assembly for CampusCLI."""

from typing import List, Optional
from campuscli.config import CampusConfig
from campuscli.core.context import build_repo_map
from campuscli.tools.base import ToolRegistry


BASE_SYSTEM_PROMPT = """You are CampusCLI, an expert, highly capable software engineering assistant and code reviewer.
You operate directly inside the user's repository, providing precise code review, debugging, refactoring, test writing, and feature development.

### CORE OPERATING PRINCIPLES:
1. **Always inspect before modifying**: Use `read_file` or `search_files` to understand surrounding code before making edits.
2. **Targeted Diffs over Full Rewrites**: When modifying existing code, prioritize `replace_in_file` to keep edits clean and minimize regressions. Use `write_file` when creating new files or when completely rewriting small files.
3. **Validate Changes**: When appropriate, run tests or syntax checks via `execute_command` to verify correctness.
4. **Safety First**: Do not execute destructive commands. If an action could lose data, warn the user.
5. **Clear, Actionable Code Reviews**: When reviewing code:
   - Identify bugs, edge cases, and performance/security bottlenecks.
   - Point out specific files and line numbers.
   - Provide concrete fix recommendations.

### REPOSITORY CONTEXT:
{repo_context}

{tool_calling_instructions}
"""

XML_TOOL_INSTRUCTIONS = """
### AVAILABLE TOOLS:
You have access to the following tools:
{tool_schemas}

To invoke a tool, output an XML tool block formatted exactly like this:
<tool_call>
<name>TOOL_NAME</name>
<arguments>
{{"param1": "value1", "param2": "value2"}}
</arguments>
</tool_call>

You can provide explanation before or after calling a tool. Once the tool finishes, you will receive a `<tool_result>` block.
"""


def build_system_prompt(
    config: CampusConfig,
    registry: ToolRegistry,
    custom_instructions: Optional[str] = None
) -> str:
    """Construct full system prompt with repository map and tool definitions."""
    repo_map = build_repo_map(config.workspace_root)

    tool_instructions = ""
    if config.llm.force_xml_tools:
        tool_instructions = XML_TOOL_INSTRUCTIONS.format(
            tool_schemas=registry.to_xml_prompt()
        )

    prompt = BASE_SYSTEM_PROMPT.format(
        repo_context=repo_map,
        tool_calling_instructions=tool_instructions
    )

    if config.custom_system_prompt:
        prompt += f"\n\n### USER CUSTOM INSTRUCTIONS:\n{config.custom_system_prompt}"

    if custom_instructions:
        prompt += f"\n\n### TASK-SPECIFIC INSTRUCTIONS:\n{custom_instructions}"

    return prompt
