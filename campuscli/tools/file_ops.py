"""File system operations for CampusCLI."""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional
from campuscli.tools.base import default_registry


@default_registry.register(
    name="read_file",
    description="Read content of a file with optional line ranges."
)
def read_file(file_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
    """Read the contents of a file, optionally within a line range (1-indexed)."""
    path = Path(file_path).resolve()
    if not path.is_file():
        return f"Error: File '{file_path}' does not exist."

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        total_lines = len(lines)
        if total_lines == 0:
            return "(Empty file)"

        s_line = max(1, start_line) if start_line is not None else 1
        e_line = min(total_lines, end_line) if end_line is not None else total_lines

        if s_line > total_lines:
            return f"Error: start_line {s_line} is greater than total lines {total_lines}."

        result_lines = []
        for i in range(s_line, e_line + 1):
            line_str = lines[i - 1].rstrip("\r\n")
            result_lines.append(f"{i:4d} | {line_str}")

        header = f"--- {file_path} (Lines {s_line}-{e_line} of {total_lines}) ---\n"
        return header + "\n".join(result_lines)
    except Exception as e:
        return f"Error reading file '{file_path}': {str(e)}"


@default_registry.register(
    name="write_file",
    description="Create or completely overwrite a file with given content."
)
def write_file(file_path: str, content: str, overwrite: bool = True) -> str:
    """Write content to a file. Automatically creates parent directories."""
    path = Path(file_path).resolve()
    if path.exists() and not overwrite:
        return f"Error: File '{file_path}' already exists and overwrite is set to False."

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote {len(content.splitlines())} lines to '{file_path}'."
    except Exception as e:
        return f"Error writing to file '{file_path}': {str(e)}"


@default_registry.register(
    name="replace_in_file",
    description="Replace a target block of text with replacement content in an existing file."
)
def replace_in_file(file_path: str, target_content: str, replacement_content: str) -> str:
    """Search for target_content in file and replace it with replacement_content."""
    path = Path(file_path).resolve()
    if not path.is_file():
        return f"Error: File '{file_path}' does not exist."

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            original = f.read()

        # Try exact match first
        if target_content in original:
            occurrences = original.count(target_content)
            if occurrences > 1:
                return (
                    f"Error: target_content found {occurrences} times in '{file_path}'. "
                    "Please provide more surrounding context to make the match unique."
                )
            new_content = original.replace(target_content, replacement_content, 1)
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
            return f"Successfully replaced target content in '{file_path}'."

        # Fallback: line-stripped normalization matching
        orig_lines = original.splitlines(keepends=True)
        target_lines = [l.strip() for l in target_content.splitlines() if l.strip()]

        if not target_lines:
            return "Error: target_content is empty."

        match_start = -1
        for i in range(len(orig_lines)):
            if orig_lines[i].strip() == target_lines[0]:
                matched = True
                for j in range(1, len(target_lines)):
                    if i + j >= len(orig_lines) or orig_lines[i + j].strip() != target_lines[j]:
                        matched = False
                        break
                if matched:
                    if match_start != -1:
                        return f"Error: Multiple matching blocks found in '{file_path}'. Provide more context."
                    match_start = i

        if match_start != -1:
            match_end = match_start + len(target_lines)
            prefix = "".join(orig_lines[:match_start])
            suffix = "".join(orig_lines[match_end:])
            new_content = prefix + replacement_content + "\n" + suffix
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
            return f"Successfully replaced normalized target block in '{file_path}'."

        return f"Error: target_content was not found in '{file_path}'. Make sure exact text matches."
    except Exception as e:
        return f"Error modifying file '{file_path}': {str(e)}"


@default_registry.register(
    name="list_directory",
    description="List files and directories within a target path."
)
def list_directory(dir_path: str = ".", recursive: bool = False, max_depth: int = 2) -> str:
    """List directory contents."""
    path = Path(dir_path).resolve()
    if not path.is_dir():
        return f"Error: Path '{dir_path}' is not a directory."

    try:
        entries: List[str] = []
        base_depth = len(path.parts)

        if recursive:
            for root, dirs, files in os.walk(path):
                # filter hidden / venv
                dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("venv", ".venv", "node_modules", "__pycache__")]
                curr_depth = len(Path(root).parts) - base_depth
                if curr_depth > max_depth:
                    continue

                rel_root = os.path.relpath(root, path)
                indent = "  " * curr_depth
                if rel_root != ".":
                    entries.append(f"{indent}📁 {os.path.basename(root)}/")

                file_indent = "  " * (curr_depth + (1 if rel_root != "." else 0))
                for f in sorted(files):
                    if not f.startswith("."):
                        f_path = os.path.join(root, f)
                        size = os.path.getsize(f_path)
                        entries.append(f"{file_indent}📄 {f} ({size} bytes)")
        else:
            for item in sorted(path.iterdir()):
                if item.name.startswith(".") or item.name in ("venv", ".venv", "__pycache__", "node_modules"):
                    continue
                if item.is_dir():
                    entries.append(f"📁 {item.name}/")
                else:
                    entries.append(f"📄 {item.name} ({item.stat().st_size} bytes)")

        if not entries:
            return f"Directory '{dir_path}' is empty."
        return "\n".join(entries)
    except Exception as e:
        return f"Error listing directory '{dir_path}': {str(e)}"


@default_registry.register(
    name="search_files",
    description="Search for a text pattern or regex across files in a directory."
)
def search_files(query: str, dir_path: str = ".", file_pattern: Optional[str] = None) -> str:
    """Search for string or pattern in files."""
    path = Path(dir_path).resolve()
    if not path.is_dir():
        return f"Error: Directory '{dir_path}' not found."

    results = []
    try:
        regex = re.compile(query, re.IGNORECASE)
    except Exception as e:
        return f"Invalid search pattern '{query}': {e}"

    ignored_dirs = {".git", ".venv", "venv", "__pycache__", "node_modules", "dist", "build"}

    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith(".")]

        for file in files:
            if file.startswith("."):
                continue
            if file_pattern and not file.endswith(file_pattern.replace("*", "")):
                continue

            full_file_path = os.path.join(root, file)
            rel_file_path = os.path.relpath(full_file_path, path)

            try:
                with open(full_file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, 1):
                        if regex.search(line):
                            results.append(f"{rel_file_path}:{line_num}: {line.strip()[:150]}")
                            if len(results) >= 50:
                                results.append("... (results capped at 50 matches)")
                                return "\n".join(results)
            except Exception:
                continue

    if not results:
        return f"No matches found for '{query}' in '{dir_path}'."
    return "\n".join(results)
