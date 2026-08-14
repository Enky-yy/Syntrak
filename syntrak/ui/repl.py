"""Interactive Prompt Toolkit REPL for Syntrak."""

import asyncio
from pathlib import Path
from typing import Optional
from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion, PathCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style

from syntrak.core.session import SessionManager
from syntrak.ui.commands import execute_and_stream, handle_slash_command
from syntrak.ui.renderer import console, print_banner


SLASH_COMMANDS = [
    ("/review", "Run automated code review on current changes"),
    ("/diff", "Show git diff of working tree"),
    ("/commit", "Generate commit message and stage/commit"),
    ("/model", "Switch or view active LLM model"),
    ("/undo", "Rollback to previous git snapshot"),
    ("/compact", "Compact chat history to save context"),
    ("/clear", "Clear chat memory"),
    ("/config", "Show current configuration"),
    ("/help", "Show help menu"),
    ("/exit", "Exit session"),
]


class SyntrakCompleter(Completer):
    """Custom auto-completer for slash commands and workspace file paths."""

    def __init__(self):
        self.path_completer = PathCompleter(expanduser=True)

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if text.startswith("/"):
            word = text.strip()
            for cmd, desc in SLASH_COMMANDS:
                if cmd.startswith(word):
                    yield Completion(
                        cmd,
                        start_position=-len(text),
                        display=cmd,
                        display_meta=desc
                    )
        elif "@" in text or "/" in text or "." in text:
            yield from self.path_completer.get_completions(document, complete_event)


async def start_repl(session: Optional[SessionManager] = None):
    """Run interactive Syntrak REPL session."""
    if session is None:
        session = SessionManager()

    history_file = Path.home() / ".syntrak" / "history"
    history_file.parent.mkdir(parents=True, exist_ok=True)

    prompt_session = PromptSession(
        history=FileHistory(str(history_file)),
        auto_suggest=AutoSuggestFromHistory(),
        completer=SyntrakCompleter(),
        style=Style.from_dict({
            "prompt": "bold #00d7ff",
            "arrow": "#ff5f87 bold",
        })
    )

    print_banner(session.config.llm.model, session.config.workspace_root)

    while True:
        try:
            user_input = await prompt_session.prompt_async(
                [("class:prompt", "\nsyntrak"), ("class:arrow", " ❯ ")],
            )
            text = user_input.strip()
            if not text:
                continue

            if text.startswith("/"):
                handled = await handle_slash_command(text, session)
                if text.lower() in ("/exit", "/quit"):
                    break
                if handled:
                    continue

            # Standard user query / instruction
            await execute_and_stream(session, text)

        except (KeyboardInterrupt, asyncio.CancelledError):
            console.print("\n[yellow]Query interrupted (Ctrl+C).[/yellow]")
            continue
        except EOFError:
            console.print("\n[yellow]Goodbye![/yellow]")
            break
        except Exception as e:
            console.print(f"\n[error]Unexpected error: {str(e)}[/error]")
