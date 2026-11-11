"""Handler for ``contractguard_validate_request``."""

from __future__ import annotations

import json
import logging
from typing import Any

from ..adapters.clock import UtcClock
from ..adapters.repositories import SqliteRunRepository, SqliteServiceRepository
from ..adapters.spec_loader import SpecLoader
from ..config import Settings
from ..domain.errors import ContractGuardError
from ..domain.models import Coverage, RunType, Verdict
from ..services.evidence import record_run
from ..services.preflight import run_preflight

logger = logging.getLogger(__name__)


def validate_request(args: dict[str, Any], **kwargs: Any) -> str:
    """Validate a proposed request without sending it."""
    _ = kwargs
    service_id = args.get("service_id")
    operation_id = args.get("operation_id")
    if not isinstance(service_id, str) or not service_id.strip():
        return _error("INCOMPLETE", "service_id must be a non-empty string")
    if not isinstance(operation_id, str) or not operation_id.strip():
        return _error("INCOMPLETE", "operation_id must be a non-empty string")

    path_params = args.get("path_params", {})
    query_params = args.get("query_params", {})
    headers = args.get("headers", {})
    body = args.get("body")
    content_type = args.get("content_type")
    if not isinstance(path_params, dict):
        return _error("INCOMPLETE", "path_params must be an object")
    if not isinstance(query_params, dict):
        return _error("INCOMPLETE", "query_params must be an object")
    if not isinstance(headers, dict):
        return _error("INCOMPLETE", "headers must be an object")
    if content_type is not None and not isinstance(content_type, str):
        return _error("INCOMPLETE", "content_type must be a string")

    try:
        settings = Settings.from_env()
        from ..adapters.sqlite import open_plugin_database

        connection = open_plugin_database()
        try:
            service_repository = SqliteServiceRepository(connection)
            run_repository = SqliteRunRepository(connection)
            loader = SpecLoader(max_spec_bytes=settings.max_spec_bytes)
            started_at = UtcClock().now()
            result = run_preflight(
                loader=loader,
                service_repository=service_repository,
                service_id=service_id,
                operation_id=operation_id,
                path_params=path_params,
                query_params=query_params,
                headers=headers,
                body=body,
                content_type=content_type,
                max_body_bytes=settings.max_request_body_bytes,
            )
            receipt = record_run(
                run_repository=run_repository,
                service_id=service_id,
                run_type=RunType.PREFLIGHT,
                verdict=Verdict(result.verdict),
                spec_sha256=result.spec_sha256,
                started_at=started_at,
                duration_ms=0,
                operation_id=operation_id,
                violations=result.violations,
                coverage=Coverage(executed=1),
            )
            payload = result.to_dict()
            payload["run_id"] = receipt.run_id
            return json.dumps(payload, separators=(",", ":"))
        finally:
            connection.close()
    except ContractGuardError as exc:
        return json.dumps(exc.as_dict(), separators=(",", ":"))
    except Exception as exc:  # pragma: no cover
        logger.exception("Unexpected error during preflight for %s", service_id)
        payload = {"code": "CONTRACTGUARD_ERROR", "message": str(exc)}
        return json.dumps(payload, separators=(",", ":"))


def _error(code: str, message: str) -> str:
    return json.dumps({"code": code, "message": message}, separators=(",", ":"))
