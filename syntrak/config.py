"""Configuration management for Syntrak."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMConfig(BaseModel):
    """Configuration for LLM model and endpoint."""
    model: str = Field(
        default="ollama/qwen2.5-coder:latest",
        description="Model name, e.g., 'ollama/qwen2.5-coder:latest', 'ollama/deepseek-coder-v2', 'openai/gpt-4o', etc."
    )
    api_base: Optional[str] = Field(
        default=None,
        description="Custom API Base URL (e.g., http://localhost:11434 for Ollama, http://localhost:8000/v1 for vLLM)"
    )
    api_key: Optional[str] = Field(
        default=None,
        description="API key for commercial providers or authenticated endpoints"
    )
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=128)
    context_window: int = Field(
        default=32768,
        description="Maximum context window of the target model for compaction"
    )
    force_xml_tools: bool = Field(
        default=False,
        description="Force XML/markdown tool calling fallback instead of JSON function calling"
    )


class SecurityConfig(BaseModel):
    """Security and execution boundaries."""
    require_confirmation_for_bash: bool = True
    require_confirmation_for_file_delete: bool = True
    blocked_commands: List[str] = Field(
        default_factory=lambda: [
            "rm -rf /",
            "mkfs",
            ":(){ :|:& };:",
            "dd if=",
            "shutdown",
            "reboot"
        ]
    )
    max_bash_timeout_seconds: int = 60


class ReviewConfig(BaseModel):
    """Configuration for the automated code reviewer."""
    guidelines: List[str] = Field(
        default_factory=lambda: [
            "Ensure rigorous error handling and input validation",
            "Identify security vulnerabilities (OWASP, SQLi, injection, auth leaks)",
            "Verify edge cases and boundary conditions",
            "Check for performance bottlenecks or unbounded loops/queries",
            "Ensure adherence to clean code and project idioms"
        ]
    )
    strictness: str = Field(default="medium", description="low | medium | high | strict")


class SyntrakConfig(BaseSettings):
    """Main Syntrak configuration."""
    model_config = SettingsConfigDict(
        env_prefix="CAMPUSCLI_",
        env_nested_delimiter="__",
        extra="ignore"
    )

    llm: LLMConfig = Field(default_factory=LLMConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    review: ReviewConfig = Field(default_factory=ReviewConfig)

    max_agent_steps: int = Field(default=25, description="Maximum ReAct steps per query")
    enable_git_snapshots: bool = Field(default=True, description="Take git stashes/checkpoints before major changes")
    custom_system_prompt: Optional[str] = None
    workspace_root: str = Field(default_factory=os.getcwd)

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "SyntrakConfig":
        """Load config from ~/.syntrak/config.yaml, local .syntrakrc.yaml, or path."""
        data: Dict[str, Any] = {}

        global_path = Path.home() / ".syntrak" / "config.yaml"
        local_path = Path.cwd() / ".syntrakrc.yaml"

        paths_to_check = []
        if config_path:
            paths_to_check.append(Path(config_path))
        else:
            paths_to_check.extend([global_path, local_path])

        for path in paths_to_check:
            if path.is_file():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        file_data = yaml.safe_load(f) or {}
                        data.update(file_data)
                except Exception as e:
                    print(f"Warning: Failed to load config from {path}: {e}")

        # If LLM model is not explicitly defined in file, check popular env vars
        if "llm" not in data:
            data["llm"] = {}
        if "api_key" not in data["llm"] and os.getenv("OPENAI_API_KEY"):
            data["llm"]["api_key"] = os.getenv("OPENAI_API_KEY")
        if "api_base" not in data["llm"] and os.getenv("OLLAMA_HOST"):
            data["llm"]["api_base"] = os.getenv("OLLAMA_HOST")

        return cls(**data)

    def save_global(self) -> Path:
        """Save current config to global ~/.syntrak/config.yaml."""
        dest = Path.home() / ".syntrak" / "config.yaml"
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            yaml.dump(self.model_dump(), f, default_flow_style=False)
        return dest
