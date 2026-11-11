"""Ports (interfaces) that the service layer depends on.

These protocols are the dependency-inversion boundary. Services accept ports;
composition roots supply concrete adapters. Implementations must translate
library-specific objects into the domain models in :mod:`contractguard.domain.models`
and must not leak external exception types across this boundary.

All ports are synchronous by design (ADR-003).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Protocol

from .models import (
    Baseline,
    EvidenceReceipt,
    Finding,
    HttpRequest,
    HttpResponse,
    InspectionReport,
    LoadedSpec,
    Operation,
    ServiceRegistration,
    SpecSnapshot,
)


class Clock(Protocol):
    """Source of timezone-aware UTC timestamps."""

    def now(self) -> datetime:
        """Return the current time as an aware UTC ``datetime``."""
        ...


class SpecLoader(Protocol):
    """Load and validate OpenAPI documents into domain snapshots."""

    def inspect(self, path: Path) -> InspectionReport:
        """Inspect one local OpenAPI document.

        Implementations enforce the file-size cap, reject external ``$ref``
        values, validate the document, and build the operation inventory.

        Args:
            path: Exact local path supplied by the user.

        Returns:
            A complete inspection report, including ``VALID``, ``INVALID_SPEC``,
            or ``UNSUPPORTED`` status.
        """
        ...

    def load_file(self, path: Path) -> LoadedSpec:
        """Read, parse, validate, and normalize a local JSON/YAML document.

        Implementations enforce the file-size cap, reject external ``$ref``
        values, and raise domain errors from :mod:`contractguard.domain.errors`.

        Args:
            path: Exact local path supplied by the user.

        Returns:
            The parsed document and its snapshot metadata.

        Raises:
            SpecLoadError: The file cannot be read or parsed.
            SpecValidationError: The document is not a supported OpenAPI document.
        """
        ...

    def load_document(
        self,
        document: Mapping[str, object],
        *,
        source_name: str,
    ) -> LoadedSpec:
        """Validate and normalize an in-memory document (for example a baseline).

        Args:
            document: Parsed JSON mapping.
            source_name: Human-readable provenance label.

        Returns:
            The normalized document and its snapshot metadata.

        Raises:
            SpecValidationError: The document is not a supported OpenAPI document.
        """
        ...


class ContractValidator(Protocol):
    """Validate requests and responses against an OpenAPI snapshot."""

    def validate_request(
        self,
        *,
        snapshot: SpecSnapshot,
        operation: Operation,
        request: HttpRequest,
    ) -> Sequence[Finding]:
        """Validate a proposed request without performing any I/O.

        Args:
            snapshot: Contract snapshot containing the operation.
            operation: Resolved operation definition.
            request: Transport-neutral request to validate.

        Returns:
            All detected findings; an empty sequence means the request matches
            the declared shape.
        """
        ...

    def validate_response(
        self,
        *,
        snapshot: SpecSnapshot,
        operation: Operation,
        response: HttpResponse,
    ) -> Sequence[Finding]:
        """Validate an already-captured response against its declared schema.

        Args:
            snapshot: Contract snapshot containing the operation.
            operation: Resolved operation definition.
            response: Bounded response captured by the HTTP adapter.

        Returns:
            All detected findings; an empty sequence means the response matches
            the declared shape.
        """
        ...


class HttpTransport(Protocol):
    """Bounded HTTP transport used only for live GET/HEAD verification."""

    def send(self, request: HttpRequest, *, timeout_seconds: float) -> HttpResponse:
        """Send exactly one request and return a bounded response.

        The implementation must enforce loopback-only targets, GET/HEAD only,
        redirect refusal, TLS verification, ``trust_env=False``, and the
        response byte cap. It must not retry.

        Args:
            request: Request to send.
            timeout_seconds: Total request budget.

        Returns:
            The captured response.

        Raises:
            PolicyError: The target or method violates policy.
            IncompleteInputError: The response could not be read within limits.
        """
        ...


class ServiceRepository(Protocol):
    """Persistence port for registered services."""

    def get(self, service_id: str) -> ServiceRegistration | None:
        """Return a registered service, or ``None`` when it does not exist."""
        ...

    def save(self, service: ServiceRegistration) -> None:
        """Insert or update a service registration.

        Must not modify an approved baseline.

        Raises:
            StorageError: The write failed.
        """
        ...


class BaselineRepository(Protocol):
    """Persistence port for immutable, content-addressed baselines."""

    def current(self, service_id: str) -> Baseline | None:
        """Return the currently approved baseline for a service."""
        ...

    def get(self, baseline_id: str) -> Baseline | None:
        """Return a baseline by ID, including historical versions."""
        ...

    def versions(self, service_id: str, *, limit: int) -> Sequence[Baseline]:
        """Return recent baselines, newest first, bounded by ``limit``."""
        ...

    def add(self, baseline: Baseline) -> Baseline:
        """Insert a baseline row without changing the current baseline."""
        ...

    def promote(self, baseline: Baseline, *, expected_current_id: str | None) -> Baseline:
        """Add a new current baseline using transactional compare-and-swap.

        Implementations verify ``expected_current_id`` inside the transaction,
        insert a new row, and flip the current flag without mutating history.
        Promotion must never be implicit.

        Args:
            baseline: New baseline to promote.
            expected_current_id: Baseline the caller believes is current, or
                ``None`` when no baseline exists yet.

        Returns:
            The persisted baseline.

        Raises:
            StorageError: The write failed or the current baseline changed.
        """
        ...


class RunRepository(Protocol):
    """Persistence port for reduced evidence receipts and findings."""

    def record(self, receipt: EvidenceReceipt, findings: Sequence[Finding]) -> tuple[str, ...]:
        """Persist one run and its redacted findings in a single transaction.

        Returns:
            The identifiers of the stored findings.
        """
        ...

    def recent(self, service_id: str, *, limit: int) -> Sequence[EvidenceReceipt]:
        """Return recent receipts, newest first, bounded by ``limit``."""
        ...
