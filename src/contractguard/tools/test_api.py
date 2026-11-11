"""Handler for ``contractguard_test``."""

from __future__ import annotations

import json
import logging
from typing import Any

from ..adapters.clock import UtcClock
from ..adapters.http_transport import HttpxTransport
from ..adapters.repositories import SqliteRunRepository, SqliteServiceRepository
from ..adapters.spec_loader import SpecLoader
from ..config import Settings
from ..domain.errors import ContractGuardError
from ..domain.models import Coverage, RunType, Verdict
from ..services.evidence import record_run
from ..services.live_test import run_live_test

logger = logging.getLogger(__name__)


def test_api(args: dict[str, Any], **kwargs: Any) -> str:
    """Execute a bounded live GET/HEAD request and validate the response."""
    _ = kwargs
    service_id = args.get("service_id")
    operation_id = args.get("operation_id")
    if not isinstance(service_id, str) or not service_id.strip():
        return _error("INCOMPLETE", "service_id must be a non-empty string")
    if not isinstance(operation_id, str) or not operation_id.strip():
        return _error("INCOMPLETE", "operation_id must be a non-empty string")

    path_params = args.get("path_params", {})
    query_params = args.get("query_params", {})
    if not isinstance(path_params, dict):
        return _error("INCOMPLETE", "path_params must be an object")
    if not isinstance(query_params, dict):
        return _error("INCOMPLETE", "query_params must be an object")

    max_response_bytes = args.get("max_response_bytes")
    settings = Settings.from_env()
    if max_response_bytes is None:
        max_response_bytes = settings.max_response_bytes
    if not isinstance(max_response_bytes, int) or isinstance(max_response_bytes, bool):
        return _error("INCOMPLETE", "max_response_bytes must be an integer")
    max_response_bytes = min(max(1, max_response_bytes), settings.max_response_bytes)

    try:
        from ..adapters.sqlite import open_plugin_database

        connection = open_plugin_database()
        try:
            service_repository = SqliteServiceRepository(connection)
            run_repository = SqliteRunRepository(connection)
            loader = SpecLoader(max_spec_bytes=settings.max_spec_bytes)
            transport = HttpxTransport(max_response_bytes=max_response_bytes)
            started_at = UtcClock().now()
            result = run_live_test(
                loader=loader,
                service_repository=service_repository,
                transport=transport,
                service_id=service_id,
                operation_id=operation_id,
                path_params=path_params,
                query_params=query_params,
                timeout_seconds=settings.http_timeout_seconds,
                max_response_bytes=max_response_bytes,
            )
            receipt = record_run(
                run_repository=run_repository,
                service_id=service_id,
                run_type=RunType.LIVE_TEST,
                verdict=Verdict(result.verdict),
                spec_sha256=result.spec_sha256,
                started_at=started_at,
                duration_ms=result.duration_ms,
                operation_id=operation_id,
                violations=result.violations,
                coverage=Coverage(
                    executed=1 if result.request_sent else 0,
                    skipped=0 if result.request_sent else 1,
                ),
            )
            payload = result.to_dict()
            payload["run_id"] = receipt.run_id
            return json.dumps(payload, separators=(",", ":"))
        finally:
            connection.close()
    except ContractGuardError as exc:
        return json.dumps(exc.as_dict(), separators=(",", ":"))
    except Exception as exc:  # pragma: no cover
        logger.exception("Unexpected error during live test for %s", service_id)
        payload = {"code": "CONTRACTGUARD_ERROR", "message": str(exc)}
        return json.dumps(payload, separators=(",", ":"))


def _error(code: str, message: str) -> str:
    return json.dumps({"code": code, "message": message}, separators=(",", ":"))
