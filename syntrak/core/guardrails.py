"""Safety and Prompt Policy Guardrails for Syntrak."""

import re
from typing import List, Optional, Tuple


# Regex patterns and signature phrases that violate app safety fundamentals
PROMPT_INJECTION_PATTERNS = [
    r"(?i)\bignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules|commands)\b",
    r"(?i)\bdisregard\s+(all\s+)?(previous|prior|system)\s+(instructions|directives|rules)\b",
    r"(?i)\byou\s+are\s+now\s+in\s+(developer|unrestricted|god|dan|jailbreak)\s+mode\b",
    r"(?i)\boverride\s+(system|safety|security)\s+(prompt|filters|guardrails|policies)\b",
    r"(?i)\bpretend\s+you\s+have\s+no\s+(rules|restrictions|filters|guidelines)\b",
    r"(?i)\bact\s+as\s+(an\s+unrestricted|a\s+malicious|a\s+hacked)\s+(ai|assistant|agent)\b",
]

SECRET_EXFILTRATION_PATTERNS = [
    r"(?i)\b(print|show|dump|leak|reveal|output|display)\s+(all\s+)?(environment\s+variables|env\s+vars|os\.environ)\b",
    r"(?i)\b(print|reveal|leak|show)\s+(the\s+)?(jwt_secret|jwt\s+secret|api_key|api\s+token|github_token)\b",
    r"(?i)\b(cat|read|show)\s+(/\.env|~/\.syntrak/\.env|/etc/shadow|/etc/master\.passwd)\b",
    r"(?i)\b(dump|steal|extract)\s+(passwords|credentials|private\s+keys|id_rsa)\b",
]

MALICIOUS_EXPLOIT_PATTERNS = [
    r"(?i)\b(write|create|generate|code)\s+(a\s+)?(ransomware|keylogger|rootkit|trojan|spyware|polymorphic\s+virus)\b",
    r"(?i)\b(ddos|dos)\s+(attack\s+script|tool\s+to\s+crash|packet\s+flood)\b",
    r"(?i)\b(exploit|hack|bypass|crack)\s+(into\s+someone\'?s|remote\s+server|unauthorized\s+network)\b",
    r"(?i)\b(create|generate)\s+(a\s+reverse\s+shell\s+payload|meterpreter\s+payload|c2\s+beacon)\b",
]

HOST_COMPROMISE_PATTERNS = [
    r"(?i)\b(wipe|destroy|format)\s+(the\s+)?(hard\s*drive|root\s+filesystem|host\s+machine|disk)\b",
    r"(?i)\b(rm\s+-rf\s+/|mkfs\.\w+|:\(\)\{\s*:\|:&\s*\};:)\b",
    r"(?i)\b(shutdown|reboot|poweroff|init\s+0)\s+(the\s+server|the\s+host|this\s+machine)\b",
]


ALL_POLICY_CHECKS: List[Tuple[List[str], str]] = [
    (
        PROMPT_INJECTION_PATTERNS,
        "System prompt subversion / instruction override attempt"
    ),
    (
        SECRET_EXFILTRATION_PATTERNS,
        "Attempt to extract server secrets, private credentials, or environment variables"
    ),
    (
        MALICIOUS_EXPLOIT_PATTERNS,
        "Generation of malicious exploits, ransomware, keyloggers, or offensive cyber weapons"
    ),
    (
        HOST_COMPROMISE_PATTERNS,
        "Destructive host server commands or system compromise attempt"
    ),
]


def validate_prompt_safety(query: str, mode: str = "chat") -> Optional[str]:
    """
    Validate an incoming user prompt against safety and policy fundamentals.

    Returns:
        Refusal message string if a violation is detected, otherwise None.
    """
    if not query:
        return None

    cleaned = query.strip()

    for patterns, reason in ALL_POLICY_CHECKS:
        for pattern in patterns:
            if re.search(pattern, cleaned):
                return (
                    f"⚠️ **Request Blocked by Safety Policy**\n\n"
                    f"I cannot fulfill this request because it violates application fundamentals:\n"
                    f"- **Reason**: {reason}.\n\n"
                    f"Please reformulate your prompt to focus on legitimate development, code review, or general inquiries."
                )

    return None
