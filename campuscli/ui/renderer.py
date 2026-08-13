"""Rich terminal renderer for CampusCLI."""

import json
from typing import Any, Dict, Optional
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.theme import Theme

# Custom modern theme
custom_theme = Theme({
    "info": "dim cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "tool_name": "bold magenta",
    "thought": "italic dark_sea_green",
    "highlight": "bold cyan",
})

console = Console(theme=custom_theme)


def print_banner(model_name: str, workspace_root: str):
    """Print welcoming CampusCLI banner."""
    content = f"""[bold cyan]CampusCLI[/bold cyan] [dim]v0.1.0[/dim] - Open-Source Agentic Code Reviewer & Assistant
[dim]Model:[/] [bold green]{model_name}[/] | [dim]Workspace:[/] [yellow]{workspace_root}[/]
[dim]Type [bold white]/help[/] for slash commands, or ask any coding / review question directly.[/dim]"""
    console.print(Panel(content, border_style="cyan", padding=(0, 1)))


def render_thought(thought: str):
    """Render LLM thinking process."""
    pass    
    # console.print(f"[thought] {thought}[/thought]", end="")


def render_tool_start(tool_name: str, args: Dict[str, Any]):
    """Render a clean card when a tool execution starts."""
    args_str = json.dumps(args, indent=2)
    if len(args_str) > 200:
        args_str = args_str[:200] + "\n..."
    console.print(
        Panel(
            Syntax(args_str, "json", theme="monokai", line_numbers=False),
            title=f"[tool_name]⚙️ Tool Executing: {tool_name}[/tool_name]",
            border_style="magenta",
            padding=(0, 1)
        )
    )


def render_tool_result(tool_name: str, success: bool, output: Any, error: Optional[str] = None):
    """Render tool execution output or error."""
    if success:
        out_str = str(output)
        if len(out_str.splitlines()) > 15:
            preview_lines = out_str.splitlines()[:12]
            preview = "\n".join(preview_lines) + f"\n... ({len(out_str.splitlines()) - 12} more lines)"
        else:
            preview = out_str

        console.print(
            Panel(
                preview,
                title=f"[success]✓ {tool_name} Finished[/success]",
                border_style="green",
                padding=(0, 1)
            )
        )
    else:
        console.print(
            Panel(
                f"[error]{error or output}[/error]",
                title=f"[error]✗ {tool_name} Failed[/error]",
                border_style="red",
                padding=(0, 1)
            )
        )


def render_diff(diff_text: str):
    """Render syntax highlighted unified diff."""
    if not diff_text or diff_text == "No diff detected.":
        console.print("[info]No changes detected in working tree.[/info]")
        return
    syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=True)
    console.print(Panel(syntax, title="[bold yellow]Git Diff[/bold yellow]", border_style="yellow"))


def render_help():
    """Display interactive slash commands guide."""
    table = Table(title="CampusCLI Commands", border_style="cyan", show_header=True, header_style="bold cyan")
    table.add_column("Command", style="bold white", width=18)
    table.add_column("Description", style="dim")

    table.add_row("/review", "Analyze unstaged/staged git diff for bugs, style & security")
    table.add_row("/diff", "Inspect current repository changes in syntax-highlighted diff")
    table.add_row("/commit", "Generate an intelligent commit message and stage/commit")
    table.add_row("/model [name]", "Show or switch active LLM (e.g. /model ollama/qwen2.5-coder:32b)")
    table.add_row("/undo", "Rollback to previous git snapshot checkpoint")
    table.add_row("/clear", "Clear conversation history & reset memory")
    table.add_row("/compact", "Manually compact and summarize chat history")
    table.add_row("/config", "Print active configuration & endpoint settings")
    table.add_row("/help", "Show this help table")
    table.add_row("/exit, /quit", "Exit the CampusCLI interactive session")

    console.print(table)
