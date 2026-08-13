"""Base tool definitions and tool registry for Syntrak."""

import inspect
import json
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, ConfigDict


class ToolParam(BaseModel):
    name: str
    type: str
    description: str
    required: bool = True
    default: Optional[Any] = None


class ToolDefinition(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    parameters: Dict[str, Any]
    func: Optional[Callable] = None

    def to_openai_schema(self) -> Dict[str, Any]:
        """Convert to standard OpenAI / LiteLLM function calling schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }

    def to_xml_schema(self) -> str:
        """Convert tool schema to markdown/XML format for models without native tool calling."""
        props = self.parameters.get("properties", {})
        required = self.parameters.get("required", [])
        params_str = []
        for prop_name, prop_info in props.items():
            req_tag = " (required)" if prop_name in required else " (optional)"
            desc = prop_info.get("description", "")
            p_type = prop_info.get("type", "string")
            params_str.append(f"  - {prop_name}: {p_type}{req_tag} - {desc}")

        params_block = "\n".join(params_str) if params_str else "  None"
        return f"- `{self.name}`: {self.description}\n  Parameters:\n{params_block}"


class ToolRegistry:
    """Registry holding all available tools for the agent."""

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, name: Optional[str] = None, description: Optional[str] = None):
        """Decorator to register a python function as an agent tool."""
        def decorator(func: Callable):
            tool_name = name or func.__name__
            tool_desc = description or (func.__doc__ or "No description provided.").strip()

            sig = inspect.signature(func)
            properties = {}
            required = []

            type_map = {
                str: "string",
                int: "integer",
                float: "number",
                bool: "boolean",
                list: "array",
                dict: "object"
            }

            for param_name, param in sig.parameters.items():
                if param_name in ("self", "cls"):
                    continue

                # Infer type
                param_type = "string"
                if param.annotation != inspect.Parameter.empty:
                    param_type = type_map.get(param.annotation, "string")

                properties[param_name] = {
                    "type": param_type,
                    "description": f"Parameter {param_name}"
                }

                if param.default == inspect.Parameter.empty:
                    required.append(param_name)

            tool_def = ToolDefinition(
                name=tool_name,
                description=tool_desc,
                parameters={
                    "type": "object",
                    "properties": properties,
                    "required": required
                },
                func=func
            )
            self._tools[tool_name] = tool_def
            return func

        return decorator

    def get(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def list_tools(self) -> List[ToolDefinition]:
        return list(self._tools.values())

    def to_openai_tools(self) -> List[Dict[str, Any]]:
        return [t.to_openai_schema() for t in self._tools.values()]

    def to_xml_prompt(self) -> str:
        schemas = [t.to_xml_schema() for t in self._tools.values()]
        return "\n\n".join(schemas)

    async def execute(self, name: str, arguments: Dict[str, Any]) -> Any:
        tool = self.get(name)
        if not tool or not tool.func:
            raise ValueError(f"Tool '{name}' is not registered.")

        # Check if function is async
        if inspect.iscoroutinefunction(tool.func):
            return await tool.func(**arguments)
        else:
            return tool.func(**arguments)


# Global default registry
default_registry = ToolRegistry()
