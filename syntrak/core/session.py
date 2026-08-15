"""Session manager coordinating Agent, Memory, Tools, and Configuration."""

import subprocess
from typing import Any, AsyncGenerator, Dict, List, Optional
from syntrak.config import SyntrakConfig
from syntrak.core.agent import AgentRunner
from syntrak.core.events import BaseEvent
from syntrak.core.memory import MemoryManager
from syntrak.core.prompt import build_system_prompt
from syntrak.llm.litellm_client import LiteLLMClient
from syntrak.tools.base import ToolRegistry, default_registry
import syntrak.tools.file_ops  # noqa: F401 - register tools
import syntrak.tools.bash_ops  # noqa: F401 - register tools
import syntrak.tools.git_ops   # noqa: F401 - register tools
import syntrak.tools.review_ops # noqa: F401 - register tools


class SessionManager:
    """Manages an active Syntrak coding & review session."""

    def __init__(self, config: Optional[SyntrakConfig] = None):
        import os
        self.config = config or SyntrakConfig.load()
        if self.config.workspace_root:
            os.environ["SYNTRAK_WORKSPACE_ROOT"] = str(self.config.workspace_root)
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

    def set_workspace(self, workspace_root: str):
        """Switch active workspace directory for all tools and repository maps."""
        import os
        self.config.workspace_root = workspace_root
        os.environ["SYNTRAK_WORKSPACE_ROOT"] = str(workspace_root)
        self.reset_memory()

    def reset_memory(self):
        """Clear in-memory conversation buffer."""
        self.memory.clear()

    def sync_conversation_history(self, db_messages: List[Dict[str, Any]]):
        """Sync in-memory agent messages with historical messages from database."""
        self.memory.clear()
        for msg in db_messages:
            role = msg.get("role")
            content = msg.get("content")
            if role in ("user", "assistant", "system") and content:
                self.memory.add_message(role=role, content=content)

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
        custom_instructions: Optional[str] = None,
        mode: str = "chat",
        repo_authorized: bool = False
    ) -> AsyncGenerator[BaseEvent, None]:
        """Execute a user query through the agent or chat assistant with appropriate system prompt and tools."""
        enable_tools = (mode == "agent" and repo_authorized)

        if enable_tools and self.config.enable_git_snapshots:
            self.save_checkpoint(f"Pre-query: {query[:30]}")

        sys_prompt = build_system_prompt(
            config=self.config,
            registry=self.registry,
            custom_instructions=custom_instructions,
            mode=mode,
            repo_authorized=repo_authorized
        )

        async for event in self.agent.run(
            user_query=query,
            system_prompt=sys_prompt,
            enable_tools=enable_tools
        ):
            yield event

