"""Code review analysis tools for Syntrak."""

import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
from syntrak.tools.base import default_registry
from syntrak.tools.git_ops import git_diff


@default_registry.register(
    name="analyze_diff_for_review",
    description="Parse and structure diffs to prepare them for detailed code review."
)
def analyze_diff_for_review(staged: bool = False, target_branch: Optional[str] = None) -> str:
    """Analyze current repository diff and return structured metrics and changed file blocks."""
    raw_diff = git_diff(staged=staged, target_branch=target_branch)
    if raw_diff == "No diff detected.":
        recent_diff = git_diff(target_branch="HEAD~1")
        if recent_diff and recent_diff != "No diff detected.":
            raw_diff = recent_diff
        else:
            ws = os.environ.get("SYNTRAK_WORKSPACE_ROOT")
            repo_name = Path(ws).name if ws else "connected repository"
            return f"Working tree clean in repository '{repo_name}'. No uncommitted or staged changes detected to review."

    file_diffs = re.split(r"^diff --git ", raw_diff, flags=re.MULTILINE)
    file_diffs = [d for d in file_diffs if d.strip()]

    summary_lines = [f"Found {len(file_diffs)} modified files in diff:"]
    total_additions = 0
    total_deletions = 0

    structured_files = []
    for fdiff in file_diffs:
        header_match = re.search(r"a/(\S+)\s+b/(\S+)", fdiff)
        fname = header_match.group(2) if header_match else "unknown_file"

        additions = len(re.findall(r"^\+[^+]", fdiff, flags=re.MULTILINE))
        deletions = len(re.findall(r"^-[^-]", fdiff, flags=re.MULTILINE))

        total_additions += additions
        total_deletions += deletions

        summary_lines.append(f"- {fname} (+{additions} / -{deletions})")
        structured_files.append(f"### File: {fname}\n```diff\n{fdiff[:3000]}\n```")

    summary_lines.append(f"\nTotal: +{total_additions} additions, -{total_deletions} deletions\n")
    return "\n".join(summary_lines) + "\n\n" + "\n\n".join(structured_files)
