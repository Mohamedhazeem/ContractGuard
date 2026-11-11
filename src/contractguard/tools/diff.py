"""Handler for ``contractguard_diff``."""

from __future__ import annotations

import json
import logging
from typing import Any

from ..adapters.clock import UtcClock
from ..adapters.repositories import SqliteBaselineRepository, SqliteRunRepository
from ..adapters.spec_loader import SpecLoader
from ..config import Settings
from ..domain.errors import ContractGuardError
from ..domain.models import Coverage, RunType, Verdict
from ..services.diff import diff_contract
from ..services.evidence import record_run

logger = logging.getLogger(__name__)


def diff_contract_tool(args: dict[str, Any], **kwargs: Any) -> str:
    """Compare a candidate contract with the approved baseline."""
    _ = kwargs
    service_id = args.get("service_id")
    candidate_spec_path = args.get("candidate_spec_path")
    if not isinstance(service_id, str) or not service_id.strip():
        return _error("INCOMPLETE", "service_id must be a non-empty string")
    if not isinstance(candidate_spec_path, str) or not candidate_spec_path.strip():
        return _error("INCOMPLETE", "candidate_spec_path must be a non-empty string")

    try:
        settings = Settings.from_env()
        from ..adapters.sqlite import open_plugin_database

        connection = open_plugin_database()
        try:
            baseline_repository = SqliteBaselineRepository(connection)
            run_repository = SqliteRunRepository(connection)
            loader = SpecLoader(max_spec_bytes=settings.max_spec_bytes)
            started_at = UtcClock().now()
            report = diff_contract(
                baseline_repository=baseline_repository,
                loader=loader,
                service_id=service_id,
                candidate_spec_path=candidate_spec_path,
            )
            violations = [finding.to_dict() for finding in report.findings]
            verdict = Verdict.FAIL if report.breaking_count else Verdict.PASS
            receipt = record_run(
                run_repository=run_repository,
                service_id=service_id,
                run_type=RunType.DIFF,
                verdict=verdict,
                spec_sha256=report.candidate_sha256,
                started_at=started_at,
                duration_ms=0,
                operation_id=None,
                violations=violations,
                coverage=Coverage(executed=1),
            )
            payload = report.to_dict()
            payload["run_id"] = receipt.run_id
            return json.dumps(payload, separators=(",", ":"))
        finally:
            connection.close()
    except ContractGuardError as exc:
        return json.dumps(exc.as_dict(), separators=(",", ":"))
    except Exception as exc:  # pragma: no cover
        logger.exception("Unexpected error while diffing for %s", service_id)
        return json.dumps(
            {"code": "CONTRACTGUARD_ERROR", "message": str(exc)}, separators=(",", ":")
        )


def _error(code: str, message: str) -> str:
    return json.dumps({"code": code, "message": message}, separators=(",", ":"))
