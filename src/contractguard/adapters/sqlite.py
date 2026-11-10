"""SQLite schema and connection primitives for ContractGuard.

Repositories are intentionally not implemented during Stage 0. This module
establishes the storage contract and keeps every SQLite detail out of the domain
and service layers.

Runtime state is stored through Hermes' documented plugin storage helper
(``plugin_db("contractguard")``), never inside the plugin installation
directory. ``open_plugin_database`` imports that helper lazily so tests and
packaging do not require a Hermes installation at import time.

The schema follows ADR-002: baselines are immutable, content-addressed rows.
Promotion inserts a new row and flips ``is_current`` inside one transaction; the
partial unique index enforces a single current baseline per service.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import cast

from ..config import PLUGIN_NAME
from ..domain.errors import StorageError

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS services (
    service_id   TEXT PRIMARY KEY,
    spec_path    TEXT NOT NULL,
    base_url     TEXT NOT NULL,
    environment  TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS baselines (
    baseline_id        TEXT PRIMARY KEY,
    service_id         TEXT NOT NULL,
    version_label      TEXT,
    spec_sha256        TEXT NOT NULL,
    spec_json          TEXT NOT NULL,
    parent_baseline_id TEXT,
    promoted_at        TEXT NOT NULL,
    is_current         INTEGER NOT NULL DEFAULT 0 CHECK (is_current IN (0, 1)),
    FOREIGN KEY (service_id) REFERENCES services (service_id),
    FOREIGN KEY (parent_baseline_id) REFERENCES baselines (baseline_id)
);

CREATE INDEX IF NOT EXISTS ix_baselines_service
    ON baselines (service_id, promoted_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS ux_baselines_current
    ON baselines (service_id)
    WHERE is_current = 1;

CREATE TABLE IF NOT EXISTS runs (
    run_id        TEXT PRIMARY KEY,
    service_id    TEXT NOT NULL,
    operation_id  TEXT,
    run_type      TEXT NOT NULL,
    spec_sha256   TEXT NOT NULL,
    verdict       TEXT NOT NULL,
    coverage_json TEXT NOT NULL,
    started_at    TEXT NOT NULL,
    duration_ms   INTEGER,
    plugin_version TEXT NOT NULL,
    FOREIGN KEY (service_id) REFERENCES services (service_id)
);

CREATE INDEX IF NOT EXISTS ix_runs_service
    ON runs (service_id, started_at DESC);

CREATE TABLE IF NOT EXISTS findings (
    finding_id   TEXT PRIMARY KEY,
    run_id       TEXT NOT NULL,
    severity     TEXT NOT NULL,
    code         TEXT NOT NULL,
    operation_id TEXT,
    json_pointer TEXT,
    details_json TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs (run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_findings_run
    ON findings (run_id);
"""


def connect(database: str | Path = ":memory:") -> sqlite3.Connection:
    """Open a SQLite connection with ContractGuard's required pragmas.

    Args:
        database: File path or ``":memory:"``. Use a temporary path in tests
            that need multiple connections; use a single shared connection for
            an in-memory database.

    Returns:
        A connection whose rows behave like mappings and whose foreign keys are
        enforced. WAL is enabled for file-backed databases only.
    """
    target = str(database)
    connection = sqlite3.connect(target)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    if target != ":memory:":
        connection.execute("PRAGMA journal_mode = WAL")
    return connection


def initialize(connection: sqlite3.Connection) -> None:
    """Create the schema if it does not already exist.

    The operation is idempotent and does not delete data. Callers that manage
    transactions own the commit boundary; this helper commits the DDL so the
    schema is visible to subsequent statements.

    Args:
        connection: Open SQLite connection.

    Raises:
        sqlite3.Error: If the schema cannot be applied.
    """
    connection.executescript(SCHEMA_SQL)
    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    connection.commit()


def open_plugin_database() -> sqlite3.Connection:
    """Open and initialize the Hermes-managed ContractGuard database.

    The import is intentionally lazy: importing this module must not require a
    Hermes runtime, and plugin registration must perform no storage work.

    Returns:
        An initialized connection to ``plugin_db("contractguard")``.

    Raises:
        StorageError: If the Hermes storage helper is unavailable or the schema
            cannot be initialized.
    """
    try:
        from plugins.plugin_storage import plugin_db
    except ImportError as exc:
        raise StorageError(
            "Hermes plugin storage is unavailable; ContractGuard must run inside "
            "a Hermes installation that provides plugins.plugin_storage."
        ) from exc

    try:
        connection = cast(sqlite3.Connection, plugin_db(PLUGIN_NAME))
        initialize(connection)
    except sqlite3.Error as exc:
        raise StorageError("Could not open the ContractGuard plugin database.") from exc
    return connection
