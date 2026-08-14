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


def load_env_file(filepath: Path, override_environ: bool = True) -> Dict[str, str]:
    """Parse and load key-value pairs from a .env file into os.environ and return dict."""
    env_vars: Dict[str, str] = {}
    if not filepath.is_file():
        return env_vars
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip()
                    # Strip wrapping quotes
                    if len(value) >= 2 and ((value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'"))):
                        value = value[1:-1]
                    if key:
                        env_vars[key] = value
                        if override_environ or key not in os.environ:
                            os.environ[key] = value
                            if key == "GOOGLE_CLIENT_ID":
                                os.environ["SYNTRAK_GOOGLE_CLIENT_ID"] = value
                            elif key in ("LLM_MODEL", "MODEL"):
                                os.environ["SYNTRAK_LLM__MODEL"] = value
                            elif key in ("LLM_API_BASE", "API_BASE"):
                                os.environ["SYNTRAK_LLM__API_BASE"] = value
                            elif key in ("LLM_API_KEY", "API_KEY"):
                                os.environ["SYNTRAK_LLM__API_KEY"] = value
    except Exception as e:
        print(f"Warning: Failed to load .env file from {filepath}: {e}")
    return env_vars


class SyntrakConfig(BaseSettings):
    """Main Syntrak configuration."""
    model_config = SettingsConfigDict(
        env_prefix="SYNTRAK_",
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
    google_client_id: Optional[str] = Field(default=None, description="Google OAuth 2.0 Client ID for Web UI authentication")

    @classmethod
    def load(cls, config_path: Optional[str] = None, workspace_root: Optional[str] = None, env_file: Optional[str] = None) -> "SyntrakConfig":
        """Load config from .env files, ~/.syntrak/config.yaml, local .syntrakrc.yaml, or path."""
        env_data: Dict[str, str] = {}
        # 1. Discover and load .env files
        if env_file:
            env_data.update(load_env_file(Path(env_file)))
        else:
            if workspace_root:
                env_data.update(load_env_file(Path(workspace_root) / ".env"))
            env_data.update(load_env_file(Path.cwd() / ".env"))
            env_data.update(load_env_file(Path.home() / ".syntrak" / ".env"))

        data: Dict[str, Any] = {}

        global_path = Path.home() / ".syntrak" / "config.yaml"
        local_path = Path.cwd() / ".syntrakrc.yaml"

        if config_path:
            path = Path(config_path)
            if path.is_file():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data.update(yaml.safe_load(f) or {})
                except Exception as e:
                    print(f"Warning: Failed to load config from {path}: {e}")
        else:
            if global_path.is_file():
                try:
                    with open(global_path, "r", encoding="utf-8") as f:
                        global_data = yaml.safe_load(f) or {}
                        # Global config should not hardcode project workspace_root
                        global_data.pop("workspace_root", None)
                        data.update(global_data)
                except Exception as e:
                    print(f"Warning: Failed to load global config from {global_path}: {e}")

            if local_path.is_file():
                try:
                    with open(local_path, "r", encoding="utf-8") as f:
                        local_data = yaml.safe_load(f) or {}
                        data.update(local_data)
                except Exception as e:
                    print(f"Warning: Failed to load local config from {local_path}: {e}")

        # Check LLM model & keys from .env and environment variables
        if "llm" not in data:
            data["llm"] = {}

        # .env values explicitly override YAML config
        model_env = env_data.get("LLM_MODEL") or env_data.get("MODEL")
        if model_env or "model" not in data["llm"]:
            model_val = model_env or os.getenv("SYNTRAK_LLM_MODEL") or os.getenv("LLM_MODEL") or os.getenv("MODEL")
            if model_val:
                data["llm"]["model"] = model_val

        key_env = (
            env_data.get("LLM_API_KEY") or
            env_data.get("OPENAI_API_KEY") or
            env_data.get("ANTHROPIC_API_KEY") or
            env_data.get("GEMINI_API_KEY") or
            env_data.get("GROQ_API_KEY") or
            env_data.get("NVIDIA_API_KEY")
        )
        if key_env or "api_key" not in data["llm"]:
            key_val = (
                key_env or
                os.getenv("SYNTRAK_LLM_API_KEY") or
                os.getenv("LLM_API_KEY") or
                os.getenv("OPENAI_API_KEY") or
                os.getenv("ANTHROPIC_API_KEY") or
                os.getenv("GEMINI_API_KEY") or
                os.getenv("GROQ_API_KEY") or
                os.getenv("NVIDIA_API_KEY")
            )
            if key_val:
                data["llm"]["api_key"] = key_val

        base_env = env_data.get("LLM_API_BASE") or env_data.get("API_BASE")
        if base_env or "api_base" not in data["llm"]:
            base_val = base_env or os.getenv("SYNTRAK_LLM_API_BASE") or os.getenv("LLM_API_BASE") or os.getenv("API_BASE") or os.getenv("OLLAMA_HOST")
            if base_val:
                data["llm"]["api_base"] = base_val

        gid_env = env_data.get("GOOGLE_CLIENT_ID") or env_data.get("SYNTRAK_GOOGLE_CLIENT_ID")
        if gid_env or "google_client_id" not in data or not data["google_client_id"]:
            gid_val = gid_env or os.getenv("SYNTRAK_GOOGLE_CLIENT_ID") or os.getenv("GOOGLE_CLIENT_ID")
            if gid_val:
                data["google_client_id"] = gid_val

        if workspace_root:
            data["workspace_root"] = str(Path(workspace_root).resolve())
        elif "workspace_root" not in data or not data["workspace_root"]:
            data["workspace_root"] = os.getcwd()
        else:
            data["workspace_root"] = str(Path(data["workspace_root"]).resolve())

        return cls(**data)

    def save_global(self) -> Path:
        """Save current config to global ~/.syntrak/config.yaml."""
        dest = Path.home() / ".syntrak" / "config.yaml"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dump_data = self.model_dump()
        # Global config should not pin a single directory as the workspace
        dump_data.pop("workspace_root", None)
        with open(dest, "w", encoding="utf-8") as f:
            yaml.dump(dump_data, f, default_flow_style=False)
        return dest
