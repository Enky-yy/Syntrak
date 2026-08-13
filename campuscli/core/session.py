"""Session manager coordinating Agent, Memory, Tools, and Configuration."""

import subprocess
from typing import AsyncGenerator, Dict, List, Optional
from campuscli.config import CampusConfig
from campuscli.core.agent import AgentRunner
from campuscli.core.events import BaseEvent
from campuscli.core.memory import MemoryManager
from campuscli.core.prompt import build_system_prompt
from campuscli.llm.litellm_client import LiteLLMClient
from campuscli.tools.base import ToolRegistry, default_registry
import campuscli.tools.file_ops  # noqa: F401 - register tools
import campuscli.tools.bash_ops  # noqa: F401 - register tools
import campuscli.tools.git_ops   # noqa: F401 - register tools
import campuscli.tools.review_ops # noqa: F401 - register tools


class SessionManager:
    """Manages an active CampusCLI coding & review session."""

    def __init__(self, config: Optional[CampusConfig] = None):
        self.config = config or CampusConfig.load()
        self.registry: ToolRegistry = default_registry
        self.memory: MemoryManager = MemoryManager(
            context_limit=self.config.llm.context_window
        )
        self.llm: LiteLLMClient = LiteLLMClient(self.config.llm)
        self.agent: AgentRunner = AgentRunner(
            llm_client=self.llm,
            tool_registry=self.registry,
            memory_manager=self.memory,
            max_steps=self.config.max_agent_steps
        )
        self.undo_stack: List[str] = []

    def set_model(self, model_name: str, api_base: Optional[str] = None, api_key: Optional[str] = None):
        """Switch active model and provider."""
        self.config.llm.model = model_name
        if api_base is not None:
            self.config.llm.api_base = api_base
        if api_key is not None:
            self.config.llm.api_key = api_key
        self.llm = LiteLLMClient(self.config.llm)
        self.agent.llm = self.llm

    def save_checkpoint(self, description: str = "Auto-checkpoint") -> Optional[str]:
        """Save git stash commit hash as an undo point."""
        try:
            res = subprocess.run(
                ["git", "stash", "create", description],
                cwd=self.config.workspace_root,
                capture_output=True,
                text=True,
                check=False
            )
            commit_hash = res.stdout.strip()
            if commit_hash:
                self.undo_stack.append(commit_hash)
                return commit_hash
        except Exception:
            pass
        return None

    def undo_last_change(self) -> str:
        """Rollback workspace to the previous git checkpoint if available."""
        if not self.undo_stack:
            return "No previous checkpoint found in undo stack."
        last_hash = self.undo_stack.pop()
        try:
            res = subprocess.run(
                ["git", "stash", "apply", last_hash],
                cwd=self.config.workspace_root,
                capture_output=True,
                text=True,
                check=False
            )
            if res.returncode != 0:
                return f"Undo failed: {res.stderr.strip()}"
            return f"Successfully restored workspace from snapshot {last_hash[:8]}."
        except Exception as e:
            return f"Failed to execute undo: {str(e)}"

    async def execute_query(
        self,
        query: str,
        custom_instructions: Optional[str] = None
    ) -> AsyncGenerator[BaseEvent, None]:
        """Execute a user query through the agent with fresh system prompt."""
        if self.config.enable_git_snapshots:
            self.save_checkpoint(f"Pre-query: {query[:30]}")

        sys_prompt = build_system_prompt(
            config=self.config,
            registry=self.registry,
            custom_instructions=custom_instructions
        )

        async for event in self.agent.run(user_query=query, system_prompt=sys_prompt):
            yield event
