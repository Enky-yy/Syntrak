"""Git operations and repository versioning tools for CampusCLI."""

import os
from pathlib import Path
from typing import Dict, List, Optional
from campuscli.tools.base import default_registry


def _run_git(args: List[str], cwd: Optional[str] = None) -> str:
    import subprocess
    work_dir = cwd or os.getcwd()
    try:
        res = subprocess.run(
            ["git"] + args,
            cwd=work_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        if res.returncode != 0:
            return f"Git error (exit {res.returncode}): {res.stderr.strip()}"
        return res.stdout.strip()
    except FileNotFoundError:
        return "Error: git executable not found on system PATH."
    except Exception as e:
        return f"Git command failed: {str(e)}"


@default_registry.register(
    name="git_status",
    description="Check the current Git repository status (modified, untracked, and staged files)."
)
def git_status() -> str:
    """Returns the working tree git status."""
    res = _run_git(["status", "--short", "--branch"])
    if not res:
        return "Working tree clean. No changes."
    return res


@default_registry.register(
    name="git_diff",
    description="Get diff of uncommitted changes, staged changes, or compare against a branch."
)
def git_diff(staged: bool = False, target_branch: Optional[str] = None, file_path: Optional[str] = None) -> str:
    """Get git diff output."""
    args = ["diff"]
    if staged:
        args.append("--staged")
    if target_branch:
        args.append(target_branch)
    if file_path:
        args.extend(["--", file_path])

    diff_out = _run_git(args)
    if not diff_out:
        return "No diff detected."
    return diff_out


@default_registry.register(
    name="git_log",
    description="Show recent git commit history."
)
def git_log(limit: int = 5) -> str:
    """Get recent commit logs."""
    return _run_git(["log", f"-n{limit}", "--oneline", "--decorate"])


@default_registry.register(
    name="git_commit",
    description="Stage and commit changes with a descriptive commit message."
)
def git_commit(message: str, stage_all: bool = True) -> str:
    """Stage changes and commit."""
    if stage_all:
        add_res = _run_git(["add", "-A"])
        if "Git error" in add_res:
            return f"Failed to stage changes: {add_res}"

    commit_res = _run_git(["commit", "-m", message])
    return commit_res


def create_git_snapshot(description: str = "auto-checkpoint") -> Optional[str]:
    """Create a temporary git stash checkpoint before applying agent changes."""
    status = _run_git(["status", "--porcelain"])
    if not status:
        return None
    res = _run_git(["stash", "create", description])
    return res if res else None
