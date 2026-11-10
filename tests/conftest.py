"""Shared pytest fixtures for ContractGuard.

The fixtures here are deliberately small and deterministic:

- ``mock_openapi_spec`` and ``mock_openapi_spec_path`` expose the canonical
  Giftshop document under ``tests/fixtures/openapi/``.
- ``sqlite_db`` provides an initialized in-memory database with foreign keys
  enforced, using the same DDL as the runtime adapter.
- ``settings`` provides conservative default settings.

Unit tests must remain independent of a Hermes installation. Importing the
adapter here is safe because Hermes storage is imported lazily inside
``open_plugin_database``.
"""

from __future__ import annotations

import sqlite3
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from contractguard.adapters.sqlite import connect, initialize  # noqa: E402
from contractguard.config import Settings  # noqa: E402

_FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Absolute path to the shared fixtures directory."""
    return _FIXTURES


@pytest.fixture
def mock_openapi_spec_path() -> Path:
    """Path to the canonical OpenAPI 3.0 fixture."""
    return _FIXTURES / "openapi" / "giftshop.yaml"


@pytest.fixture
def mock_openapi_spec(mock_openapi_spec_path: Path) -> dict[str, Any]:
    """Parsed copy of the canonical OpenAPI fixture.

    The file is parsed per test so a test that mutates the mapping cannot affect
    another test.
    """
    with mock_openapi_spec_path.open("r", encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    if not isinstance(document, dict):
        raise AssertionError("OpenAPI fixture must contain a mapping at the top level")
    return document


@pytest.fixture
def sqlite_db() -> Iterator[sqlite3.Connection]:
    """Initialized in-memory SQLite database with the runtime schema."""
    connection = connect(":memory:")
    initialize(connection)
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture
def settings() -> Settings:
    """Conservative default settings for unit tests."""
    return Settings()
