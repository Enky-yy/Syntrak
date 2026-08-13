"""Slash command handler for interactive REPL session."""

from typing import Optional, Tuple
from campuscli.core.events import (
    AgentStatusEvent,
    DoneEvent,
    ErrorEvent,
    ThoughtStreamEvent,
    TokenStreamEvent,
    ToolResultEvent,
    ToolStartEvent,
)
from campuscli.core.session import SessionManager
from campuscli.tools.git_ops import git_diff
from campuscli.ui.renderer import (
    console,
    render_diff,
    render_help,
    render_thought,
    render_tool_result,
    render_tool_start,
)


async def handle_slash_command(command_str: str, session: SessionManager) -> bool:
    """Handle slash command. Returns True if handled, False if regular query."""
    parts = command_str.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if cmd in ("/exit", "/quit"):
        console.print("[yellow]Exiting CampusCLI session. Happy coding![/yellow]")
        return True

    elif cmd == "/help":
        render_help()
        return True

    elif cmd == "/diff":
        diff_output = git_diff(staged=False)
        render_diff(diff_output)
        return True

    elif cmd == "/review":
        console.print("[bold cyan]🔍 Starting automated code review...[/bold cyan]")
        review_prompt = (
            "Perform a comprehensive code review of the current changes in the repository. "
            "Inspect git status and git diff. Point out bugs, security issues, performance problems, "
            "and suggest concrete code fixes."
        )
        await execute_and_stream(session, review_prompt)
        return True

    elif cmd == "/commit":
        console.print("[bold cyan]📝 Generating commit message for current changes...[/bold cyan]")
        commit_prompt = (
            "Check git status and diff, craft a concise Conventional Commit message, "
            "and call `git_commit` to stage and commit the changes if appropriate."
        )
        await execute_and_stream(session, commit_prompt)
        return True

    elif cmd == "/model":
        if not arg:
            console.print(f"[info]Current Model:[/] [bold green]{session.config.llm.model}[/]")
            if session.config.llm.api_base:
                console.print(f"[info]API Base:[/] [dim]{session.config.llm.api_base}[/]")
            console.print("[dim]Use `/model <name>` to switch models (e.g., `/model ollama/qwen2.5-coder:32b`).[/dim]")
        else:
            session.set_model(arg.strip())
            console.print(f"[success]Switched model to:[/] [bold green]{arg.strip()}[/]")
        return True

    elif cmd == "/undo":
        result = session.undo_last_change()
        console.print(f"[warning]{result}[/warning]")
        return True

    elif cmd == "/clear":
        session.memory.clear()
        console.print("[success]Conversation memory cleared.[/success]")
        return True

    elif cmd == "/compact":
        compacted = session.memory.compact_if_needed()
        if compacted:
            console.print("[success]Conversation memory successfully compacted.[/success]")
        else:
            console.print("[info]Memory does not need compaction yet.[/info]")
        return True

    elif cmd == "/config":
        console.print(f"[bold cyan]Active Config:[/bold cyan]")
        console.print(f"  Model: [green]{session.config.llm.model}[/green]")
        console.print(f"  API Base: [dim]{session.config.llm.api_base or 'Default'}[/dim]")
        console.print(f"  Workspace: [yellow]{session.config.workspace_root}[/yellow]")
        console.print(f"  Max Steps: {session.config.max_agent_steps}")
        return True

    return False


async def execute_and_stream(session: SessionManager, query: str):
    """Execute a query and stream styled outputs in real-time."""
    current_token_stream = False
    spinner = console.status("[bold cyan]Thinking...[/bold cyan]", spinner="dots")
    spinner.start()

    try:
        async for event in session.execute_query(query):
            if isinstance(event, AgentStatusEvent):
                # Original step display (commented):
                # if current_token_stream:
                #     console.print()
                #     current_token_stream = False
                # console.print(f"[dim]Step {event.step}/{event.max_steps}[/dim]")
                
                if event.step > 1:
                    if spinner:
                        spinner.update(f"[dim cyan]Executing step {event.step}...[/dim cyan]")

            elif isinstance(event, ThoughtStreamEvent):
                render_thought(event.thought)

            elif isinstance(event, TokenStreamEvent):
                if spinner:
                    spinner.stop()
                console.print(event.token, end="")
                current_token_stream = True

            elif isinstance(event, ToolStartEvent):
                if spinner:
                    spinner.stop()
                if current_token_stream:
                    console.print()
                    current_token_stream = False
                render_tool_start(event.tool_name, event.arguments)

            elif isinstance(event, ToolResultEvent):
                render_tool_result(event.tool_name, event.success, event.output, event.error)
                if not spinner._live.is_started:
                    spinner.start()
                    spinner.update("[bold cyan]Processing results...[/bold cyan]")

            elif isinstance(event, ErrorEvent):
                if spinner:
                    spinner.stop()
                if current_token_stream:
                    console.print()
                    current_token_stream = False
                console.print(f"\n[error]Error: {event.message}[/error]")

            elif isinstance(event, DoneEvent):
                if spinner:
                    spinner.stop()
                if current_token_stream:
                    console.print()
                    current_token_stream = False
    finally:
        if spinner:
            spinner.stop()
