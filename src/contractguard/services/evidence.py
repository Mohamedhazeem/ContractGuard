"""Evidence recording helpers.

Turns tool results into redacted evidence receipts and persists them.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from ..domain.models import (
    Coverage,
    Direction,
    EvidenceReceipt,
    Finding,
    FindingCode,
    RunType,
    Severity,
    Verdict,
)
from ..domain.ports import RunRepository


def build_findings(violations: list[dict[str, Any]], operation_id: str | None) -> list[Finding]:
    """Convert tool-result violations into domain findings."""
    findings: list[Finding] = []
    for violation in violations:
        code_value = str(violation.get("code", "REQUEST_SCHEMA_TYPE_MISMATCH"))
        try:
            code = FindingCode(code_value)
        except ValueError:
            code = FindingCode.REQUEST_SCHEMA_TYPE_MISMATCH
        severity_value = str(violation.get("severity", "error"))
        known = {"error", "warning", "info"}
        severity = Severity(severity_value) if severity_value in known else Severity.ERROR
        direction_value = violation.get("direction")
        direction = None
        if isinstance(direction_value, str) and direction_value in {"REQUEST", "RESPONSE"}:
            direction = Direction(direction_value)
        pointer = violation.get("json_pointer")
        expected = violation.get("expected")
        actual = violation.get("actual")
        findings.append(
            Finding(
                code=code,
                message=str(violation.get("message", "")),
                severity=severity,
                direction=direction,
                operation_id=operation_id,
                json_pointer=pointer if isinstance(pointer, str) else None,
                expected=str(expected) if expected is not None else None,
                actual=str(actual) if actual is not None else None,
            )
        )
    return findings


def record_run(
    *,
    run_repository: RunRepository,
    service_id: str,
    run_type: RunType,
    verdict: Verdict,
    spec_sha256: str,
    started_at: datetime,
    duration_ms: int,
    operation_id: str | None,
    violations: list[dict[str, Any]],
    coverage: Coverage | None = None,
) -> EvidenceReceipt:
    """Persist one evidence receipt and its findings."""
    findings = build_findings(violations, operation_id)
    receipt = EvidenceReceipt(
        run_id="cg_" + uuid.uuid4().hex[:16],
        service_id=service_id,
        run_type=run_type,
        verdict=verdict,
        spec_sha256=spec_sha256,
        started_at=started_at,
        duration_ms=duration_ms,
        operation_id=operation_id,
        coverage=coverage if coverage is not None else Coverage(executed=1),
    )
    finding_ids = run_repository.record(receipt, findings)
    return EvidenceReceipt(
        run_id=receipt.run_id,
        service_id=receipt.service_id,
        run_type=receipt.run_type,
        verdict=receipt.verdict,
        spec_sha256=receipt.spec_sha256,
        started_at=receipt.started_at,
        duration_ms=receipt.duration_ms,
        operation_id=receipt.operation_id,
        finding_ids=finding_ids,
        coverage=receipt.coverage,
    )
