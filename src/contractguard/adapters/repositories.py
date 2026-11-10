"""SQLite repositories for services and baselines.

These classes implement the ports in :mod:`contractguard.domain.ports` and keep
all SQL details out of the service layer.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from ..domain.errors import StorageError
from ..domain.models import Baseline, ServiceRegistration


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


class SqliteServiceRepository:
    """Repository for registered services."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        connection.row_factory = sqlite3.Row
        self._connection = connection

    def get(self, service_id: str) -> ServiceRegistration | None:
        row = self._connection.execute(
            "SELECT service_id, spec_path, base_url, environment, created_at, updated_at "
            "FROM services WHERE service_id = ?",
            (service_id,),
        ).fetchone()
        if row is None:
            return None
        return ServiceRegistration(
            service_id=row["service_id"],
            spec_path=row["spec_path"],
            base_url=row["base_url"],
            environment=row["environment"],
            created_at=_parse_datetime(row["created_at"]),
            updated_at=_parse_datetime(row["updated_at"]),
        )

    def save(self, service: ServiceRegistration) -> None:
        try:
            with self._connection:
                self._connection.execute(
                    """
                    INSERT INTO services (
                        service_id, spec_path, base_url, environment, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(service_id) DO UPDATE SET
                        spec_path = excluded.spec_path,
                        base_url = excluded.base_url,
                        environment = excluded.environment,
                        updated_at = excluded.updated_at
                    """,
                    (
                        service.service_id,
                        service.spec_path,
                        service.base_url,
                        service.environment,
                        service.created_at.isoformat(),
                        service.updated_at.isoformat(),
                    ),
                )
        except sqlite3.Error as exc:
            raise StorageError("Could not save the service registration.") from exc


class SqliteBaselineRepository:
    """Repository for immutable, content-addressed baselines."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        connection.row_factory = sqlite3.Row
        self._connection = connection

    def current(self, service_id: str) -> Baseline | None:
        row = self._connection.execute(
            "SELECT baseline_id, service_id, version_label, spec_sha256, spec_json, "
            "parent_baseline_id, promoted_at, is_current "
            "FROM baselines WHERE service_id = ? AND is_current = 1",
            (service_id,),
        ).fetchone()
        return _row_to_baseline(row) if row is not None else None

    def get(self, baseline_id: str) -> Baseline | None:
        row = self._connection.execute(
            "SELECT baseline_id, service_id, version_label, spec_sha256, spec_json, "
            "parent_baseline_id, promoted_at, is_current "
            "FROM baselines WHERE baseline_id = ?",
            (baseline_id,),
        ).fetchone()
        return _row_to_baseline(row) if row is not None else None

    def versions(self, service_id: str, *, limit: int) -> list[Baseline]:
        rows = self._connection.execute(
            "SELECT baseline_id, service_id, version_label, spec_sha256, spec_json, "
            "parent_baseline_id, promoted_at, is_current "
            "FROM baselines WHERE service_id = ? ORDER BY promoted_at DESC LIMIT ?",
            (service_id, limit),
        ).fetchall()
        return [_row_to_baseline(row) for row in rows]

    def add(self, baseline: Baseline) -> Baseline:
        try:
            with self._connection:
                self._connection.execute(
                    """
                    INSERT INTO baselines (
                        baseline_id, service_id, version_label, spec_sha256, spec_json,
                        parent_baseline_id, promoted_at, is_current
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        baseline.baseline_id,
                        baseline.service_id,
                        baseline.version_label,
                        baseline.spec_sha256,
                        baseline.spec_json,
                        baseline.parent_baseline_id,
                        baseline.promoted_at.isoformat(),
                        1 if baseline.is_current else 0,
                    ),
                )
        except sqlite3.Error as exc:
            raise StorageError("Could not store the baseline.") from exc
        return baseline

    def promote(self, baseline: Baseline, *, expected_current_id: str | None) -> Baseline:
        try:
            with self._connection:
                row = self._connection.execute(
                    "SELECT baseline_id FROM baselines WHERE service_id = ? AND is_current = 1",
                    (baseline.service_id,),
                ).fetchone()
                current_id = row["baseline_id"] if row is not None else None
                if current_id != expected_current_id:
                    raise StorageError(
                        "The current baseline changed since this promotion was prepared; "
                        "reload and retry."
                    )
                self._connection.execute(
                    """
                    INSERT INTO baselines (
                        baseline_id, service_id, version_label, spec_sha256, spec_json,
                        parent_baseline_id, promoted_at, is_current
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        baseline.baseline_id,
                        baseline.service_id,
                        baseline.version_label,
                        baseline.spec_sha256,
                        baseline.spec_json,
                        baseline.parent_baseline_id,
                        baseline.promoted_at.isoformat(),
                    ),
                )
                if current_id is not None:
                    self._connection.execute(
                        "UPDATE baselines SET is_current = 0 WHERE baseline_id = ?",
                        (current_id,),
                    )
        except sqlite3.Error as exc:
            raise StorageError("Could not promote the baseline.") from exc
        return baseline


def _row_to_baseline(row: Any) -> Baseline:
    return Baseline(
        baseline_id=row["baseline_id"],
        service_id=row["service_id"],
        version_label=row["version_label"],
        spec_sha256=row["spec_sha256"],
        spec_json=row["spec_json"],
        parent_baseline_id=row["parent_baseline_id"],
        promoted_at=_parse_datetime(row["promoted_at"]),
        is_current=bool(row["is_current"]),
    )


def new_baseline_id() -> str:
    """Generate a unique baseline identifier."""
    return "bl_" + uuid.uuid4().hex
