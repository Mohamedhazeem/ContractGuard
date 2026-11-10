"""Tests for secret redaction helpers."""

from __future__ import annotations

from contractguard.adapters.redaction import is_secret_header, redact_headers, redact_text


def test_secret_headers_are_redacted_case_insensitively() -> None:
    redacted = redact_headers(
        {
            "Authorization": "Bearer secret-token",
            "Cookie": "session=abc",
            "X-API-Key": "key-123",
            "Content-Type": "application/json",
        }
    )

    assert redacted["Authorization"] == "[REDACTED]"
    assert redacted["Cookie"] == "[REDACTED]"
    assert redacted["X-API-Key"] == "[REDACTED]"
    assert redacted["Content-Type"] == "application/json"


def test_is_secret_header_recognizes_common_names() -> None:
    assert is_secret_header("Authorization")
    assert is_secret_header("  cookie ")
    assert not is_secret_header("Accept")


def test_redact_text_removes_bearer_tokens() -> None:
    text = "Authorization: Bearer abc.def-123 and api_key: supersecret"
    redacted = redact_text(text)

    assert "abc.def-123" not in redacted
    assert "supersecret" not in redacted
    assert "[REDACTED]" in redacted
