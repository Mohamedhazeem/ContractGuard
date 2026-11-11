"""Tests that the plugin version stays consistent everywhere.

The version is declared in three places: ``src/contractguard/version.py`` (what
the plugin reports at runtime), ``plugin.yaml`` (what Hermes shows), and
``pyproject.toml`` (what the package metadata says). A mismatch makes
``contractguard_ping`` report a version that does not match the installed
plugin, so it is pinned by a test.
"""

from __future__ import annotations

from pathlib import Path

import tomllib

from contractguard.version import __version__

_ROOT = Path(__file__).resolve().parents[2]


def _manifest_version() -> str:
    import yaml

    manifest = yaml.safe_load((_ROOT / "plugin.yaml").read_text(encoding="utf-8"))
    return str(manifest["version"])


def _pyproject_version() -> str:
    document = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(document["project"]["version"])


def test_versions_match() -> None:
    assert _manifest_version() == __version__
    assert _pyproject_version() == __version__
