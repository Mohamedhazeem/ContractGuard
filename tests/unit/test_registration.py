"""Tests for service registration."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from contractguard.adapters.repositories import SqliteBaselineRepository, SqliteServiceRepository
from contractguard.adapters.spec_loader import SpecLoader
from contractguard.domain.errors import PolicyError
from contractguard.services.registration import register_service

FIXTURE = Path("tests/fixtures/openapi/giftshop.yaml")


class FixedClock:
    """Deterministic clock."""

    def now(self) -> datetime:
        return datetime(2026, 11, 12, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def service_repository(sqlite_db: sqlite3.Connection) -> SqliteServiceRepository:
    return SqliteServiceRepository(sqlite_db)


@pytest.fixture
def baseline_repository(sqlite_db: sqlite3.Connection) -> SqliteBaselineRepository:
    return SqliteBaselineRepository(sqlite_db)


def test_registration_stores_an_absolute_spec_path(
    service_repository: SqliteServiceRepository,
    baseline_repository: SqliteBaselineRepository,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A relative path must survive a later check from another directory."""
    spec = tmp_path / "openapi.yaml"
    spec.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    result = register_service(
        loader=SpecLoader(max_spec_bytes=1024 * 1024),
        service_repository=service_repository,
        baseline_repository=baseline_repository,
        clock=FixedClock(),
        service_id="giftshop-api",
        base_url="http://127.0.0.1:8000",
        environment="local",
        spec_path="openapi.yaml",
    )

    assert Path(result.spec_path).is_absolute()
    assert Path(result.spec_path) == spec.resolve()

    # The stored registration points at the resolved path, so a check that
    # runs from an unrelated working directory still finds the contract.
    stored = service_repository.get("giftshop-api")
    assert stored is not None
    assert Path(stored.spec_path).is_absolute()


def test_registration_rejects_a_non_loopback_target(
    service_repository: SqliteServiceRepository,
    baseline_repository: SqliteBaselineRepository,
) -> None:
    with pytest.raises(PolicyError):
        register_service(
            loader=SpecLoader(max_spec_bytes=1024 * 1024),
            service_repository=service_repository,
            baseline_repository=baseline_repository,
            clock=FixedClock(),
            service_id="giftshop-api",
            base_url="http://example.com",
            environment="local",
            spec_path=str(FIXTURE),
        )


def test_registration_stores_a_candidate_not_an_approved_baseline(
    service_repository: SqliteServiceRepository,
    baseline_repository: SqliteBaselineRepository,
) -> None:
    result = register_service(
        loader=SpecLoader(max_spec_bytes=1024 * 1024),
        service_repository=service_repository,
        baseline_repository=baseline_repository,
        clock=FixedClock(),
        service_id="giftshop-api",
        base_url="http://127.0.0.1:8000",
        environment="local",
        spec_path=str(FIXTURE),
    )

    assert result.candidate_baseline_created is True
    assert result.approved_baseline_present is False
    assert baseline_repository.current("giftshop-api") is None
