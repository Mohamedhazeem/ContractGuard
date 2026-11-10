"""Service registration use case."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from ..domain.errors import PolicyError
from ..domain.models import Baseline, LoadedSpec, ServiceRegistration
from ..domain.ports import BaselineRepository, Clock, ServiceRepository
from ..domain.ports import SpecLoader as SpecLoaderPort


@dataclass(frozen=True, slots=True)
class RegistrationResult:
    """Result of registering a service."""

    service_id: str
    base_url: str
    environment: str
    spec_path: str
    spec_sha256: str
    candidate_baseline_created: bool
    approved_baseline_present: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "service_id": self.service_id,
            "base_url": self.base_url,
            "environment": self.environment,
            "spec_path": self.spec_path,
            "spec_sha256": self.spec_sha256,
            "candidate_baseline_created": self.candidate_baseline_created,
            "approved_baseline_present": self.approved_baseline_present,
        }


def _is_loopback(base_url: str) -> bool:
    try:
        parts = urlsplit(base_url)
    except ValueError:
        return False
    host = parts.hostname
    return host in {"localhost", "127.0.0.1", "::1"}


def register_service(
    *,
    loader: SpecLoaderPort,
    service_repository: ServiceRepository,
    baseline_repository: BaselineRepository,
    clock: Clock,
    service_id: str,
    base_url: str,
    environment: str,
    spec_path: str,
) -> RegistrationResult:
    """Register or update a service and store its current spec as a candidate.

    Args:
        loader: Spec loader.
        service_repository: Service persistence.
        baseline_repository: Baseline persistence.
        clock: Time source.
        service_id: Service slug.
        base_url: Explicit development base URL.
        environment: Environment label.
        spec_path: Path to the OpenAPI document.

    Returns:
        Registration result.

    Raises:
        PolicyError: The base URL is not a loopback target.
        SpecValidationError: The OpenAPI document is invalid.
    """
    if not _is_loopback(base_url):
        raise PolicyError("Live targets must be loopback addresses in the MVP.")

    loaded: LoadedSpec = loader.load_file(Path(spec_path))
    sha = loaded.snapshot.sha256

    existing = service_repository.get(service_id)
    now = clock.now()
    created_at = existing.created_at if existing is not None else now
    service = ServiceRegistration(
        service_id=service_id,
        base_url=base_url,
        environment=environment,
        spec_path=spec_path,
        created_at=created_at,
        updated_at=now,
    )
    service_repository.save(service)

    current = baseline_repository.current(service_id)
    versions = baseline_repository.versions(service_id, limit=100)
    candidate_created = not any(version.spec_sha256 == sha for version in versions)

    if candidate_created:
        candidate = Baseline(
            baseline_id=uuid.uuid4().hex,
            service_id=service_id,
            spec_sha256=sha,
            spec_json=json.dumps(
                loaded.document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ),
            promoted_at=now,
            version_label=None,
            parent_baseline_id=current.baseline_id if current is not None else None,
            is_current=False,
        )
        baseline_repository.add(candidate)

    return RegistrationResult(
        service_id=service_id,
        base_url=base_url,
        environment=environment,
        spec_path=spec_path,
        spec_sha256=sha,
        candidate_baseline_created=candidate_created,
        approved_baseline_present=current is not None,
    )
