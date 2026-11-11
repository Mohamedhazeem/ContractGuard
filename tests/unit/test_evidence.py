"""Tests for evidence recording and history."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from contractguard.adapters.repositories import SqliteRunRepository
from contractguard.domain.models import (
    Coverage,
    Direction,
    EvidenceReceipt,
    FindingCode,
    RunType,
    Verdict,
)
from contractguard.services.evidence import build_findings, record_run


@pytest.fixture
def registered_service(sqlite_db: sqlite3.Connection) -> None:
    """Insert the service row the ``runs`` table references."""
    sqlite_db.execute(
        "INSERT INTO services "
        "(service_id, spec_path, base_url, environment, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            "giftshop-api",
            "tests/fixtures/openapi/giftshop.yaml",
            "http://127.0.0.1:8000",
            "local",
            "2026-11-11T10:00:00+00:00",
            "2026-11-11T10:00:00+00:00",
        ),
    )
    sqlite_db.commit()


def _receipt() -> EvidenceReceipt:
    return EvidenceReceipt(
        run_id="cg_test",
        service_id="giftshop-api",
        run_type=RunType.LIVE_TEST,
        verdict=Verdict.FAIL,
        spec_sha256="a" * 64,
        started_at=datetime(2026, 11, 11, 10, 0, tzinfo=timezone.utc),
        duration_ms=12,
        operation_id="getProduct",
        coverage=Coverage(executed=1),
    )


def test_build_findings_maps_violations() -> None:
    findings = build_findings(
        [
            {
                "code": "RESPONSE_SCHEMA_TYPE_MISMATCH",
                "json_pointer": "$.price",
                "message": "price must be a number",
                "expected": "number",
                "actual": "string",
                "direction": "RESPONSE",
            }
        ],
        "getProduct",
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.code is FindingCode.RESPONSE_SCHEMA_TYPE_MISMATCH
    assert finding.direction is Direction.RESPONSE
    assert finding.json_pointer == "$.price"
    assert finding.operation_id == "getProduct"


def test_record_run_persists_receipt_and_findings(
    sqlite_db: sqlite3.Connection, registered_service: None
) -> None:
    repository = SqliteRunRepository(sqlite_db)
    receipt = record_run(
        run_repository=repository,
        service_id="giftshop-api",
        run_type=RunType.LIVE_TEST,
        verdict=Verdict.FAIL,
        spec_sha256="a" * 64,
        started_at=datetime(2026, 11, 11, 10, 0, tzinfo=timezone.utc),
        duration_ms=12,
        operation_id="getProduct",
        violations=[
            {
                "code": "RESPONSE_SCHEMA_TYPE_MISMATCH",
                "json_pointer": "$.price",
                "message": "price must be a number",
            }
        ],
    )

    assert receipt.finding_ids
    rows = sqlite_db.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    assert rows == 1
    finding_rows = sqlite_db.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
    assert finding_rows == 1


def test_recent_returns_bounded_receipts(
    sqlite_db: sqlite3.Connection, registered_service: None
) -> None:
    repository = SqliteRunRepository(sqlite_db)
    repository.record(_receipt(), [])

    receipts = repository.recent("giftshop-api", limit=5)

    assert len(receipts) == 1
    assert receipts[0].verdict is Verdict.FAIL
    assert receipts[0].run_type is RunType.LIVE_TEST
    assert receipts[0].spec_sha256 == "a" * 64


def test_receipt_stores_no_secret_headers(
    sqlite_db: sqlite3.Connection, registered_service: None
) -> None:
    repository = SqliteRunRepository(sqlite_db)
    repository.record(_receipt(), [])

    row = sqlite_db.execute("SELECT * FROM runs").fetchone()
    assert row is not None
    assert "Authorization" not in str(tuple(row))
    assert "Bearer" not in str(tuple(row))
