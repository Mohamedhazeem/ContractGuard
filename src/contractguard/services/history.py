"""Evidence history use case."""

from __future__ import annotations

from typing import Any

from ..domain.models import EvidenceReceipt
from ..domain.ports import RunRepository


def recent_runs(
    *,
    run_repository: RunRepository,
    service_id: str,
    limit: int,
) -> list[EvidenceReceipt]:
    """Return bounded, redacted evidence receipts for a service."""
    return list(run_repository.recent(service_id, limit=limit))


def receipt_to_dict(receipt: EvidenceReceipt) -> dict[str, Any]:
    """Serialize one receipt for a tool result."""
    return {
        "run_id": receipt.run_id,
        "service_id": receipt.service_id,
        "run_type": receipt.run_type.value,
        "verdict": receipt.verdict.value,
        "operation_id": receipt.operation_id,
        "spec_sha256": receipt.spec_sha256,
        "started_at": receipt.started_at.isoformat(),
        "duration_ms": receipt.duration_ms,
        "finding_ids": list(receipt.finding_ids),
        "coverage": {
            "executed": receipt.coverage.executed,
            "skipped": receipt.coverage.skipped,
            "unsupported": receipt.coverage.unsupported,
        },
    }
