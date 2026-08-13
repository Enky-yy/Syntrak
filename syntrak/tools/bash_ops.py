"""Bash and command-line execution operations for Syntrak."""

import asyncio
import os
import shlex
from typing import Dict, List, Optional
from syntrak.tools.base import default_registry


BLOCKED_PATTERNS = [
    "rm -rf /",
    "mkfs",
    ":(){ :|:& };:",
    "dd if=/dev",
    "> /dev/sda",
    "> /dev/nvme",
    "shutdown",
    "reboot",
    "init 0"
]


@default_registry.register(
    name="execute_command",
    description="Execute a shell command with real-time output capture and safety checks."
)
async def execute_command(command: str, timeout_seconds: int = 60, cwd: Optional[str] = None) -> str:
    """Run a shell command asynchronously and return its combined stdout and stderr."""
    for pattern in BLOCKED_PATTERNS:
        if pattern in command:
            return f"Security Violation: Command '{command}' was blocked due to dangerous pattern '{pattern}'."

    # Safeguard working directory: fall back to current working dir if passed path does not exist
    if cwd and os.path.isdir(cwd):
        working_dir = cwd
    else:
        working_dir = os.getcwd()

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

        exit_code = proc.returncode
        output_parts = []
        if stdout_str:
            output_parts.append(stdout_str)
        if stderr_str:
            output_parts.append(f"[stderr]\n{stderr_str}")

        combined = "\n".join(output_parts).strip()
        if not combined:
            combined = "(No output produced)"

        return f"Exit Code: {exit_code}\nOutput:\n{combined}"
    except Exception as e:
        return f"Failed to execute command '{command}': {str(e)}"
