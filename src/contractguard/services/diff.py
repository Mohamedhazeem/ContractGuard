"""Contract compatibility diff use case."""

from __future__ import annotations

import json
from pathlib import Path

from ..domain.errors import NotFoundError
from ..domain.models import CompatibilityReport
from ..domain.ports import BaselineRepository
from ..domain.ports import SpecLoader as SpecLoaderPort
from .compatibility import RULESET_VERSION, dereference, diff_specs


def diff_contract(
    *,
    baseline_repository: BaselineRepository,
    loader: SpecLoaderPort,
    service_id: str,
    candidate_spec_path: str,
) -> CompatibilityReport:
    """Compare a candidate spec against the approved baseline."""
    baseline = baseline_repository.current(service_id)
    if baseline is None:
        raise NotFoundError(f"No approved baseline for service {service_id!r}.")

    loaded = loader.load_file(Path(candidate_spec_path))
    baseline_document = json.loads(baseline.spec_json)
    candidate_document = loaded.document

    baseline_document = dereference(baseline_document)
    candidate_document = dereference(candidate_document)

    findings = diff_specs(baseline_document, candidate_document)

    breaking = sum(1 for f in findings if f.classification.value == "breaking")
    potentially = sum(1 for f in findings if f.classification.value == "potentially_breaking")
    non_breaking = sum(1 for f in findings if f.classification.value == "non_breaking")
    unclassified = sum(1 for f in findings if f.classification.value == "unclassified")

    return CompatibilityReport(
        service_id=service_id,
        baseline_id=baseline.baseline_id,
        baseline_sha256=baseline.spec_sha256,
        candidate_sha256=loaded.snapshot.sha256,
        ruleset_version=RULESET_VERSION,
        breaking_count=breaking,
        potentially_breaking_count=potentially,
        non_breaking_count=non_breaking,
        unclassified_count=unclassified,
        findings=tuple(findings),
    )
