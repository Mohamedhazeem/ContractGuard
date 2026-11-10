"""Foundation tests for the scaffold.

These tests do not claim any product capability. They verify that the
configuration contract, storage schema, domain vocabulary, and shared fixtures
are wired correctly before feature slices begin.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from contractguard.adapters.sqlite import SCHEMA_VERSION
from contractguard.config import (
    DEFAULT_HTTP_TIMEOUT_SECONDS,
    DEFAULT_MAX_OPERATIONS_PER_RUN,
    DEFAULT_MAX_RESPONSE_BYTES,
    DEFAULT_MAX_SPEC_BYTES,
    ConfigurationError,
    Settings,
)
from contractguard.domain.models import (
    Direction,
    Finding,
    FindingCode,
    ServiceRegistration,
    Severity,
)


def test_default_settings_are_conservative(settings: Settings) -> None:
    assert settings.max_spec_bytes == DEFAULT_MAX_SPEC_BYTES == 2 * 1024 * 1024
    assert settings.max_response_bytes == DEFAULT_MAX_RESPONSE_BYTES == 1024 * 1024
    assert settings.http_timeout_seconds == DEFAULT_HTTP_TIMEOUT_SECONDS == 5.0
    assert settings.max_operations_per_run == DEFAULT_MAX_OPERATIONS_PER_RUN == 1


def test_settings_from_env_casts_values() -> None:
    result = Settings.from_env(
        {
            "CONTRACTGUARD_MAX_RESPONSE_BYTES": "2048",
            "CONTRACTGUARD_HTTP_TIMEOUT_SECONDS": "2.5",
            "CONTRACTGUARD_MAX_OPERATIONS_PER_RUN": "3",
        }
    )

    assert result.max_response_bytes == 2048
    assert result.http_timeout_seconds == 2.5
    assert result.max_operations_per_run == 3


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("CONTRACTGUARD_MAX_SPEC_BYTES", "two-megabytes"),
        ("CONTRACTGUARD_HTTP_TIMEOUT_SECONDS", "soon"),
        ("CONTRACTGUARD_MAX_OPERATIONS_PER_RUN", "many"),
    ],
)
def test_settings_reject_malformed_env_values(variable: str, value: str) -> None:
    with pytest.raises(ConfigurationError):
        Settings.from_env({variable: value})


@pytest.mark.parametrize(
    "overrides",
    [
        {"max_spec_bytes": 1},
        {"max_response_bytes": 0},
        {"http_timeout_seconds": 31.0},
        {"max_operations_per_run": 6},
        {"max_history_records": 21},
    ],
)
def test_settings_reject_unsafe_bounds(overrides: dict[str, int | float]) -> None:
    with pytest.raises(ConfigurationError):
        Settings(**overrides)  # type: ignore[arg-type]


def test_sqlite_schema_creates_expected_tables(sqlite_db: sqlite3.Connection) -> None:
    tables = {
        row["name"]
        for row in sqlite_db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert {"services", "baselines", "runs", "findings"} <= tables
    assert sqlite_db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert sqlite_db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


def test_current_baseline_index_is_unique(sqlite_db: sqlite3.Connection) -> None:
    indexes = {
        row["name"]
        for row in sqlite_db.execute("SELECT name FROM sqlite_master WHERE type = 'index'")
    }
    assert "ux_baselines_current" in indexes


def test_mock_spec_fixture_is_openapi_30(mock_openapi_spec: dict[str, object]) -> None:
    assert str(mock_openapi_spec["openapi"]).startswith("3.0.")
    info = mock_openapi_spec["info"]
    assert isinstance(info, dict)
    assert info["title"] == "Giftshop API"

    paths = mock_openapi_spec["paths"]
    assert isinstance(paths, dict)
    product_get = paths["/products/{product_id}"]["get"]
    assert product_get["operationId"] == "getProduct"


def test_finding_serializes_without_unset_fields() -> None:
    finding = Finding(
        code=FindingCode.RESPONSE_SCHEMA_TYPE_MISMATCH,
        message="Response field 'price' must be a number.",
        direction=Direction.RESPONSE,
        operation_id="getProduct",
        json_pointer="$.price",
        expected="number",
        actual="string",
    )

    payload = finding.to_dict()

    assert payload["code"] == "RESPONSE_SCHEMA_TYPE_MISMATCH"
    assert payload["severity"] == Severity.ERROR.value
    assert payload["json_pointer"] == "$.price"
    assert payload["direction"] == "RESPONSE"
    assert payload["expected"] == "number"


def test_service_registration_rejects_url_credentials() -> None:
    timestamp = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="URL credentials"):
        ServiceRegistration(
            service_id="giftshop-api",
            base_url="http://user:secret@127.0.0.1:8000",
            environment="local-development",
            spec_path="tests/fixtures/openapi/giftshop.yaml",
            created_at=timestamp,
            updated_at=timestamp,
        )
