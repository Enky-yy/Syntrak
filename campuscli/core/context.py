"""Repository context and file tree mapper for CampusCLI."""

import os
from pathlib import Path
from typing import List, Set


DEFAULT_IGNORED = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".idea",
    ".vscode",
    ".coverage"
}


def load_gitignore_patterns(workspace_root: str) -> Set[str]:
    patterns = set(DEFAULT_IGNORED)
    gitignore_path = Path(workspace_root) / ".gitignore"
    if gitignore_path.is_file():
        try:
            with open(gitignore_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        patterns.add(line.rstrip("/"))
        except Exception:
            pass
    return patterns


def build_repo_map(workspace_root: str = ".", max_depth: int = 3, max_files: int = 100) -> str:
    """Generate a compact directory tree and file map for prompt context."""
    root_path = Path(workspace_root).resolve()
    if not root_path.exists():
        return f"(Workspace path '{workspace_root}' not found)"

    ignored = load_gitignore_patterns(str(root_path))
    file_count = 0
    lines: List[str] = [f"Workspace Root: {root_path.name}/"]

    for root, dirs, files in os.walk(root_path):
        # Prune ignored directories in-place
        dirs[:] = [d for d in dirs if d not in ignored and not d.startswith(".")]

        rel_dir = os.path.relpath(root, root_path)
        depth = len(Path(rel_dir).parts) if rel_dir != "." else 0

        if depth > max_depth:
            continue

        indent = "  " * depth
        if rel_dir != ".":
            lines.append(f"{indent}📁 {os.path.basename(root)}/")

        file_indent = "  " * (depth + (1 if rel_dir != "." else 0))
        for file in sorted(files):
            if file.startswith(".") or file in ignored:
                continue

            file_count += 1
            if file_count > max_files:
                lines.append(f"{file_indent}... (remaining files truncated)")
                return "\n".join(lines)

            f_path = os.path.join(root, file)
            try:
                size = os.path.getsize(f_path)
                lines.append(f"{file_indent}📄 {file} ({size} B)")
            except Exception:
                lines.append(f"{file_indent}📄 {file}")

    return "\n".join(lines)
