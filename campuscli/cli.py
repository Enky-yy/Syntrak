"""Main CLI entrypoint for CampusCLI using Typer."""

import asyncio
from typing import Optional
import typer
import uvicorn

from campuscli.config import CampusConfig
from campuscli.core.session import SessionManager
from campuscli.tools.git_ops import git_diff
from campuscli.ui.commands import execute_and_stream
from campuscli.ui.renderer import console, render_diff
from campuscli.ui.repl import start_repl

app = typer.Typer(
    name="campuscli",
    help="Terminal-based & web-ready open-source code reviewer and writer assistant.",
    no_args_is_help=False
)


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    model: Optional[str] = typer.Option(None, "--model", "-m", help="LLM model (e.g. ollama/qwen2.5-coder:latest)"),
    api_base: Optional[str] = typer.Option(None, "--api-base", help="Custom API Base URL (e.g. http://localhost:11434)"),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="API key for LLM provider"),
):
    """Start interactive REPL by default if no subcommand is passed."""
    if ctx.invoked_subcommand is None:
        cfg = CampusConfig.load()
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
):
    """Run a single prompt/task non-interactively."""
    cfg = CampusConfig.load()
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
):
    """Perform automated code review on current diff."""
    cfg = CampusConfig.load()
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
):
    """Launch the Web API server (SSE / REST) to connect a Web UI."""
    console.print(f"[bold cyan]🚀 Starting CampusCLI Web API server on http://{host}:{port}[/bold cyan]")
    uvicorn.run("campuscli.server.app:app", host=host, port=port, reload=reload)


@app.command(name="init")
def init_config():
    """Create default global config file (~/.campuscli/config.yaml)."""
    cfg = CampusConfig()
    dest = cfg.save_global()
    console.print(f"[success]Created global config at:[/] [bold green]{dest}[/]")


if __name__ == "__main__":
    app()
