"""Bash and command-line execution operations for Syntrak."""

import asyncio
import os
import re
import shlex
from typing import Dict, List, Optional
from syntrak.core.agent import scrub_secrets
from syntrak.tools.base import default_registry
from syntrak.tools.file_ops import _resolve_path

BLOCKED_COMMAND_REGEXES = [
    r"(?i)\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*|-[a-zA-Z]*f[a-zA-Z]*r[a-zA-Z]*)\s+(/|/\*|--no-preserve-root)\b",
    r"(?i)\bmkfs(\.\w+)?\b",
    r":\(\)\{\s*:\|:&\s*\};:",
    r"(?i)\bdd\s+if=/dev/(zero|urandom|random|null)\s+of=/dev/",
    r"(?i)>\s*/dev/(sd[a-z]|nvme\d+n\d+|hd[a-z])",
    r"(?i)\b(shutdown|reboot|poweroff|halt|init\s+0)\b",
    r"(?i)\bchmod\s+(-R\s+)?(777|000)\s+/\b",
    r"(?i)\bchown\s+(-R\s+)?\w+\s+/\b",
    r"(?i)\bcurl\s+[^|]+\|\s*(ba|z|da|k|t?c)?sh\b",
    r"(?i)\bwget\s+[^|]+\|\s*(ba|z|da|k|t?c)?sh\b",
    r"(?i)\b(cat|head|tail|more|less|grep|awk|sed)\s+.*(/etc/shadow|/etc/master\.passwd|\.ssh/id_|\.env|pypi_token\.txt|\.token)",
]

MAX_BASH_OUTPUT_BYTES = 500 * 1024  # 500 KB limit


@default_registry.register(
    name="execute_command",
    description="Execute a shell command with real-time output capture and safety checks."
)
async def execute_command(command: str, timeout_seconds: int = 60, cwd: Optional[str] = None) -> str:
    """Run a shell command asynchronously and return its combined stdout and stderr."""
    for pattern in BLOCKED_COMMAND_REGEXES:
        if re.search(pattern, command):
            return f"Security Violation: Command '{command}' was blocked due to dangerous pattern matching."

    # Validate working directory against workspace boundary
    if cwd:
        try:
            working_dir = str(_resolve_path(cwd))
        except PermissionError as pe:
            return f"Security Violation: {str(pe)}"
    else:
        working_dir = os.environ.get("SYNTRAK_WORKSPACE_ROOT") or os.getcwd()

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=working_dir
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            return f"Error: Command timed out after {timeout_seconds} seconds."

        stdout_str = stdout.decode("utf-8", errors="replace")
        stderr_str = stderr.decode("utf-8", errors="replace")

        # Truncate output if exceeding maximum buffer
        if len(stdout_str) > MAX_BASH_OUTPUT_BYTES:
            stdout_str = stdout_str[:MAX_BASH_OUTPUT_BYTES] + "\n... [stdout truncated to 500 KB limit]"
        if len(stderr_str) > MAX_BASH_OUTPUT_BYTES:
            stderr_str = stderr_str[:MAX_BASH_OUTPUT_BYTES] + "\n... [stderr truncated to 500 KB limit]"

        exit_code = proc.returncode
        output_parts = []
        if stdout_str:
            output_parts.append(stdout_str)
        if stderr_str:
            output_parts.append(f"[stderr]\n{stderr_str}")

        combined = "\n".join(output_parts).strip()
        if not combined:
            combined = "(No output produced)"

        # Scrub sensitive credentials from shell output
        sanitized_output = scrub_secrets(combined)
        return f"Exit Code: {exit_code}\nOutput:\n{sanitized_output}"
    except Exception as e:
        return f"Failed to execute command '{command}': {str(e)}"
