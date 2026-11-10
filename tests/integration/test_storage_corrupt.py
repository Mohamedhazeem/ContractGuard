"""Integration tests for storage failure handling."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from contractguard.adapters.repositories import SqliteServiceRepository
from contractguard.domain.errors import StorageError


@pytest.mark.integration
def test_corrupt_database_raises_storage_error() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "corrupt.db"
        db_path.write_bytes(b"this is not a sqlite database")

        connection = sqlite3.connect(str(db_path))
        connection.row_factory = sqlite3.Row
        repository = SqliteServiceRepository(connection)

        with pytest.raises(StorageError):
            repository.get("any-service")

        connection.close()
