"""Main CLI entrypoint for Syntrak using Typer."""

import asyncio
from typing import Optional
import typer
import uvicorn

from syntrak.config import SyntrakConfig
from syntrak.core.session import SessionManager
from syntrak.tools.git_ops import git_diff
from syntrak.ui.commands import execute_and_stream
from syntrak.ui.renderer import console, render_diff
from syntrak.ui.repl import start_repl

app = typer.Typer(
    name="syntrak",
    help="Terminal-based & web-ready open-source code reviewer and writer assistant.",
    no_args_is_help=False
)


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    model: Optional[str] = typer.Option(None, "--model", "-m", help="LLM model (e.g. ollama/qwen2.5-coder:latest)"),
    api_base: Optional[str] = typer.Option(None, "--api-base", help="Custom API Base URL (e.g. http://localhost:11434)"),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="API key for LLM provider"),
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w", help="Workspace root directory"),
):
    """Start interactive REPL by default if no subcommand is passed."""
    if ctx.invoked_subcommand is None:
        cfg = SyntrakConfig.load(workspace_root=workspace)
        if model:
            cfg.llm.model = model
        if api_base:
            cfg.llm.api_base = api_base
        if api_key:
            cfg.llm.api_key = api_key

        session = SessionManager(config=cfg)
        asyncio.run(start_repl(session))


@app.command(name="run")
def run_command(
    query: str = typer.Argument(..., help="Prompt or task to execute"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="LLM model to use"),
    api_base: Optional[str] = typer.Option(None, "--api-base", help="Custom API Base URL"),
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w", help="Workspace root directory"),
):
    """Run a single prompt/task non-interactively."""
    cfg = SyntrakConfig.load(workspace_root=workspace)
    if model:
        cfg.llm.model = model
    if api_base:
        cfg.llm.api_base = api_base

    session = SessionManager(config=cfg)
    asyncio.run(execute_and_stream(session, query))


@app.command(name="review")
def review_command(
    staged: bool = typer.Option(False, "--staged", "-s", help="Review only staged changes"),
    target_branch: Optional[str] = typer.Option(None, "--target-branch", "-b", help="Compare against branch"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="LLM model to use"),
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w", help="Workspace root directory"),
):
    """Perform automated code review on current diff."""
    cfg = SyntrakConfig.load(workspace_root=workspace)
    if model:
        cfg.llm.model = model

    session = SessionManager(config=cfg)
    review_instruction = (
        f"Perform an in-depth code review on the {'staged' if staged else 'working tree'} changes. "
        "Inspect the git diff, find any bugs or security vulnerabilities, verify edge cases, "
        "and provide concrete fix recommendations."
    )
    asyncio.run(execute_and_stream(session, review_instruction))


@app.command(name="diff")
def diff_command(
    staged: bool = typer.Option(False, "--staged", "-s", help="Show staged diff"),
    target_branch: Optional[str] = typer.Option(None, "--target-branch", "-b", help="Compare against branch"),
):
    """Show rich syntax-highlighted git diff."""
    d = git_diff(staged=staged, target_branch=target_branch)
    render_diff(d)


@app.command(name="serve")
def serve_command(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host address to bind"),
    port: int = typer.Option(8000, "--port", "-p", help="Port number"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload for dev"),
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w", help="Workspace root directory"),
):
    """Launch the Web API server (SSE / REST) to connect a Web UI."""
    console.print(f"[bold cyan]🚀 Starting Syntrak Web API server on http://{host}:{port}[/bold cyan]")
    if workspace:
        from syntrak.server.app import create_app
        cfg = SyntrakConfig.load(workspace_root=workspace)
        server_app = create_app(config=cfg)
        uvicorn.run(server_app, host=host, port=port, reload=reload)
    else:
        uvicorn.run("syntrak.server.app:app", host=host, port=port, reload=reload)


@app.command(name="init")
def init_config():
    """Create default global config file (~/.syntrak/config.yaml)."""
    cfg = SyntrakConfig()
    dest = cfg.save_global()
    console.print(f"[success]Created global config at:[/] [bold green]{dest}[/]")


if __name__ == "__main__":
    app()
