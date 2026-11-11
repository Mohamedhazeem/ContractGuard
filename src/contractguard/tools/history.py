"""Handler for ``contractguard_history``."""

from __future__ import annotations

import json
import logging
from typing import Any

from ..adapters.repositories import SqliteRunRepository
from ..config import MAX_HISTORY_LIMIT
from ..domain.errors import ContractGuardError
from ..services.history import receipt_to_dict, recent_runs

logger = logging.getLogger(__name__)


def history(args: dict[str, Any], **kwargs: Any) -> str:
    """Return bounded, redacted evidence receipts for a service."""
    _ = kwargs
    service_id = args.get("service_id")
    if not isinstance(service_id, str) or not service_id.strip():
        return _error("INCOMPLETE", "service_id must be a non-empty string")

    limit = args.get("limit", 10)
    if not isinstance(limit, int) or isinstance(limit, bool):
        return _error("INCOMPLETE", "limit must be an integer")
    limit = max(1, min(limit, MAX_HISTORY_LIMIT))

    try:
        from ..adapters.sqlite import open_plugin_database

        connection = open_plugin_database()
        try:
            run_repository = SqliteRunRepository(connection)
            receipts = recent_runs(
                run_repository=run_repository,
                service_id=service_id,
                limit=limit,
            )
            return json.dumps(
                {
                    "service_id": service_id,
                    "limit": limit,
                    "count": len(receipts),
                    "runs": [receipt_to_dict(receipt) for receipt in receipts],
                },
                separators=(",", ":"),
            )
        finally:
            connection.close()
    except ContractGuardError as exc:
        return json.dumps(exc.as_dict(), separators=(",", ":"))
    except Exception as exc:  # pragma: no cover
        logger.exception("Unexpected error while reading history for %s", service_id)
        payload = {"code": "CONTRACTGUARD_ERROR", "message": str(exc)}
        return json.dumps(payload, separators=(",", ":"))


def _error(code: str, message: str) -> str:
    return json.dumps({"code": code, "message": message}, separators=(",", ":"))
