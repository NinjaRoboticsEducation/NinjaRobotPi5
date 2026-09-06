from __future__ import annotations

import re


PATTERNS = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "aws-access-key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "credential-assignment": re.compile(
        r"(?i)\b(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\s*[:=]\s*[\"']?[A-Za-z0-9_./+\-=]{12,}"
    ),
}


def detected_secret_kinds(text: str) -> list[str]:
    """Return pattern names only, never the sensitive matched text."""
    return [name for name, pattern in PATTERNS.items() if pattern.search(text)]
