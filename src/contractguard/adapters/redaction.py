"""Redaction helpers for secrets and sensitive values.

These helpers are the single place where secret-bearing data is stripped before
it can reach logs, findings, history, or tool output.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

REDACTED = "[REDACTED]"

SECRET_HEADERS = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "api-key",
        "x-auth-token",
    }
)


def is_secret_header(name: str) -> bool:
    """Return True when a header name carries credentials."""
    return name.strip().lower() in SECRET_HEADERS


def redact_headers(headers: Mapping[str, Any]) -> dict[str, str]:
    """Return a copy of ``headers`` with secret values replaced."""
    result: dict[str, str] = {}
    for name, value in headers.items():
        if is_secret_header(str(name)):
            result[str(name)] = REDACTED
        else:
            result[str(name)] = str(value)
    return result


def redact_text(text: str) -> str:
    """Remove common credential patterns from free-form text."""
    import re

    patterns = (
        r"Bearer\s+[A-Za-z0-9._\-]+",
        r"Basic\s+[A-Za-z0-9+/=]+",
        r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*\S+",
    )
    redacted = text
    for pattern in patterns:
        redacted = re.sub(pattern, REDACTED, redacted)
    return redacted
