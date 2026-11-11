"""Tests for resolving user-supplied paths against the session directory."""

from __future__ import annotations

from pathlib import Path

import pytest

from contractguard.tools.session_paths import resolve_user_path, session_base_dir


class _Context:
    """Minimal stand-in for the Hermes plugin context."""

    def __init__(self, cwd: str) -> None:
        self._cwd = cwd

    def session_cwd(self) -> str:
        return self._cwd


class _BrokenContext:
    """A context whose session directory is unavailable."""

    def session_cwd(self) -> str:
        raise RuntimeError("no session")


def test_relative_path_resolves_against_the_session_directory(tmp_path: Path) -> None:
    (tmp_path / "openapi.yaml").write_text("openapi: 3.0.3\n", encoding="utf-8")

    resolved = resolve_user_path(_Context(str(tmp_path)), "openapi.yaml")

    assert resolved == (tmp_path / "openapi.yaml").resolve()


def test_nested_relative_path_resolves_against_the_session_directory(tmp_path: Path) -> None:
    nested = tmp_path / "demo" / "api"
    nested.mkdir(parents=True)
    (nested / "openapi.yaml").write_text("openapi: 3.0.3\n", encoding="utf-8")

    resolved = resolve_user_path(_Context(str(tmp_path)), "demo/api/openapi.yaml")

    assert resolved == (nested / "openapi.yaml").resolve()


def test_absolute_path_is_used_as_given(tmp_path: Path) -> None:
    target = tmp_path / "openapi.yaml"
    target.write_text("openapi: 3.0.3\n", encoding="utf-8")

    resolved = resolve_user_path(_Context("/nowhere"), str(target))

    assert resolved == target.resolve()


def test_missing_file_reports_both_locations(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError) as excinfo:
        resolve_user_path(_Context(str(tmp_path)), "missing.yaml")

    message = str(excinfo.value)
    assert "missing.yaml" in message
    assert str(tmp_path) in message


def test_session_base_dir_falls_back_to_the_process_directory() -> None:
    base = session_base_dir(_BrokenContext())

    assert base == Path.cwd()
