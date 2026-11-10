"""Pure domain vocabulary and invariants.

This module uses only the Python standard library. It must never import
``httpx``, ``yaml``, ``sqlite3``, ``openapi_core``, or Hermes modules.

The records here are transport-neutral: adapters translate HTTPX responses,
SQLite rows, and library errors into these types before the service layer sees
them.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from urllib.parse import urlsplit

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SERVICE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


class Verdict(str, Enum):
    """Overall outcome of one ContractGuard check."""

    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    INCOMPLETE = "INCOMPLETE"
    INVALID_SPEC = "INVALID_SPEC"


class Severity(str, Enum):
    """Finding severity."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Direction(str, Enum):
    """Which side of the contract a finding applies to."""

    REQUEST = "REQUEST"
    RESPONSE = "RESPONSE"


class RunType(str, Enum):
    """Kind of evidence receipt recorded for a run."""

    INSPECT = "inspect"
    PREFLIGHT = "validate_request"
    LIVE_TEST = "test"
    DIFF = "diff"
    PROMOTE = "promote_baseline"


class FindingCode(str, Enum):
    """Stable machine-readable finding codes.

    These values are part of the public JSON contract. Renaming or removing one
    requires a documented migration.
    """

    # Document-level
    SPEC_VERSION_UNSUPPORTED = "SPEC_VERSION_UNSUPPORTED"
    SPEC_EXTERNAL_REF_BLOCKED = "SPEC_EXTERNAL_REF_BLOCKED"
    SPEC_OPERATION_ID_DUPLICATE = "SPEC_OPERATION_ID_DUPLICATE"
    SPEC_OPERATION_ID_MISSING = "SPEC_OPERATION_ID_MISSING"

    # Request preflight
    REQUEST_PARAMETER_MISSING = "REQUEST_PARAMETER_MISSING"
    REQUEST_REQUIRED_PROPERTY_MISSING = "REQUEST_REQUIRED_PROPERTY_MISSING"
    REQUEST_SCHEMA_TYPE_MISMATCH = "REQUEST_SCHEMA_TYPE_MISMATCH"
    REQUEST_ENUM_VALUE_INVALID = "REQUEST_ENUM_VALUE_INVALID"
    REQUEST_MEDIA_TYPE_UNDECLARED = "REQUEST_MEDIA_TYPE_UNDECLARED"

    # Live response
    RESPONSE_STATUS_UNDECLARED = "RESPONSE_STATUS_UNDECLARED"
    RESPONSE_MEDIA_TYPE_UNDECLARED = "RESPONSE_MEDIA_TYPE_UNDECLARED"
    RESPONSE_REQUIRED_PROPERTY_MISSING = "RESPONSE_REQUIRED_PROPERTY_MISSING"
    RESPONSE_SCHEMA_TYPE_MISMATCH = "RESPONSE_SCHEMA_TYPE_MISMATCH"

    # Baseline compatibility
    BASELINE_PATH_REMOVED = "BASELINE_PATH_REMOVED"
    BASELINE_OPERATION_REMOVED = "BASELINE_OPERATION_REMOVED"
    BASELINE_REQUEST_REQUIREMENT_ADDED = "BASELINE_REQUEST_REQUIREMENT_ADDED"
    BASELINE_RESPONSE_PROPERTY_REMOVED = "BASELINE_RESPONSE_PROPERTY_REMOVED"
    BASELINE_SCHEMA_TYPE_CHANGED = "BASELINE_SCHEMA_TYPE_CHANGED"
    UNCLASSIFIED_CHANGE = "UNCLASSIFIED_CHANGE"

    # Safety and transport
    TARGET_NOT_ALLOWED = "TARGET_NOT_ALLOWED"
    LIVE_METHOD_BLOCKED = "LIVE_METHOD_BLOCKED"
    SECRET_HEADER_REJECTED = "SECRET_HEADER_REJECTED"
    INPUT_EXAMPLE_MISSING = "INPUT_EXAMPLE_MISSING"
    RESPONSE_TOO_LARGE = "RESPONSE_TOO_LARGE"
    TRANSPORT_ERROR = "TRANSPORT_ERROR"
    STORAGE_ERROR = "STORAGE_ERROR"


@dataclass(frozen=True, slots=True)
class Finding:
    """One deterministic contract finding.

    Attributes:
        code: Stable finding code.
        message: Safe, human-readable explanation with no secret values.
        severity: Error, warning, or informational notice.
        direction: Request or response side, when applicable.
        operation_id: OpenAPI operation ID, when known.
        json_pointer: JSON Pointer into the request or response document.
        expected: Expected type or constraint name.
        actual: Observed type or constraint name (never a raw secret value).
    """

    code: FindingCode
    message: str
    severity: Severity = Severity.ERROR
    direction: Direction | None = None
    operation_id: str | None = None
    json_pointer: str | None = None
    expected: str | None = None
    actual: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dictionary, omitting unset fields."""
        payload: dict[str, object] = {
            "code": self.code.value,
            "severity": self.severity.value,
            "message": self.message,
        }
        if self.direction is not None:
            payload["direction"] = self.direction.value
        if self.operation_id is not None:
            payload["operation_id"] = self.operation_id
        if self.json_pointer is not None:
            payload["json_pointer"] = self.json_pointer
        if self.expected is not None:
            payload["expected"] = self.expected
        if self.actual is not None:
            payload["actual"] = self.actual
        return payload


@dataclass(frozen=True, slots=True)
class Operation:
    """One path/method pair declared by an OpenAPI document."""

    method: str
    path: str
    operation_id: str | None = None
    has_request_body: bool = False
    response_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.method or self.method != self.method.upper():
            raise ValueError("operation method must be uppercase and non-empty")
        if not self.path.startswith("/"):
            raise ValueError("operation path must start with '/'")


@dataclass(frozen=True, slots=True)
class SpecSnapshot:
    """Validated metadata for one OpenAPI document.

    The SHA-256 covers canonical JSON bytes of the parsed document, not the raw
    file bytes. See :func:`canonical_json_bytes`.
    """

    sha256: str
    openapi_version: str
    title: str
    api_version: str
    operations: tuple[Operation, ...] = ()
    source_name: str = "<memory>"

    def __post_init__(self) -> None:
        _require_sha256("sha256", self.sha256)
        _require_non_empty("openapi_version", self.openapi_version)
        _require_non_empty("title", self.title)
        _require_non_empty("api_version", self.api_version)
        _require_non_empty("source_name", self.source_name)


@dataclass(frozen=True, slots=True)
class LoadedSpec:
    """A parsed document paired with its normalized snapshot."""

    snapshot: SpecSnapshot
    document: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class HttpRequest:
    """Transport-neutral outgoing request used for preflight and live tests."""

    method: str
    url: str
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes | None = None

    def __post_init__(self) -> None:
        if not self.method or self.method != self.method.upper():
            raise ValueError("request method must be uppercase and non-empty")
        _require_non_empty("url", self.url)


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """Bounded, transport-neutral response captured from a live target."""

    status_code: int
    headers: Mapping[str, str]
    body: bytes
    elapsed_ms: int

    def __post_init__(self) -> None:
        if not 100 <= self.status_code <= 599:
            raise ValueError("status_code must be a valid HTTP status")
        if self.elapsed_ms < 0:
            raise ValueError("elapsed_ms must be non-negative")


@dataclass(frozen=True, slots=True)
class ServiceRegistration:
    """A developer-registered API target.

    ``spec_path`` is convenience provenance only. It is never the identity of an
    approved baseline (see ADR-002).
    """

    service_id: str
    base_url: str
    environment: str
    spec_path: str
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        _require_service_id(self.service_id)
        _require_http_url("base_url", self.base_url)
        _require_non_empty("environment", self.environment)
        _require_non_empty("spec_path", self.spec_path)
        _require_utc("created_at", self.created_at)
        _require_utc("updated_at", self.updated_at)
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot precede created_at")


@dataclass(frozen=True, slots=True)
class Baseline:
    """An immutable, content-addressed approved contract.

    The canonical JSON must hash to ``spec_sha256``. Constructing a baseline with
    mismatched content is a programming error and fails immediately.
    """

    baseline_id: str
    service_id: str
    spec_sha256: str
    spec_json: str
    promoted_at: datetime
    version_label: str | None = None
    parent_baseline_id: str | None = None
    is_current: bool = False

    def __post_init__(self) -> None:
        _require_non_empty("baseline_id", self.baseline_id)
        _require_service_id(self.service_id)
        _require_sha256("spec_sha256", self.spec_sha256)
        _require_utc("promoted_at", self.promoted_at)

        loaded: object = json.loads(self.spec_json)
        if not isinstance(loaded, dict):
            raise ValueError("spec_json must contain a JSON object")
        if sha256_hex(canonical_json_bytes(loaded)) != self.spec_sha256:
            raise ValueError("spec_sha256 does not match canonical spec_json bytes")


@dataclass(frozen=True, slots=True)
class Coverage:
    """Counts describing what a run actually checked."""

    executed: int = 0
    skipped: int = 0
    unsupported: int = 0

    def __post_init__(self) -> None:
        for name in ("executed", "skipped", "unsupported"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} coverage count cannot be negative")

    @property
    def total(self) -> int:
        """Total considered checks, including skipped and unsupported ones."""
        return self.executed + self.skipped + self.unsupported


@dataclass(frozen=True, slots=True)
class EvidenceReceipt:
    """Redacted, reproducible metadata for one run."""

    run_id: str
    service_id: str
    run_type: RunType
    verdict: Verdict
    spec_sha256: str
    started_at: datetime
    duration_ms: int = 0
    operation_id: str | None = None
    finding_ids: tuple[str, ...] = ()
    coverage: Coverage = Coverage()

    def __post_init__(self) -> None:
        _require_non_empty("run_id", self.run_id)
        _require_service_id(self.service_id)
        _require_sha256("spec_sha256", self.spec_sha256)
        _require_utc("started_at", self.started_at)
        if self.duration_ms < 0:
            raise ValueError("duration_ms must be non-negative")


@dataclass(frozen=True, slots=True)
class OperationDetail:
    """Inspection-level detail for one declared operation."""

    operation_id: str | None
    method: str
    path: str
    response_codes: tuple[str, ...] = ()
    has_request_body: bool = False
    required_inputs: tuple[str, ...] = ()
    examples_available: bool = False


@dataclass(frozen=True, slots=True)
class InspectionReport:
    """Result of inspecting one OpenAPI document."""

    status: str
    spec_path: str
    sha256: str
    openapi_version: str
    title: str
    api_version: str
    operation_count: int
    operations: tuple[OperationDetail, ...] = ()
    errors: tuple[str, ...] = ()
    coverage_gaps: tuple[str, ...] = ()
    unsupported_constructs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in {"VALID", "INVALID_SPEC", "UNSUPPORTED"}:
            raise ValueError("status must be VALID, INVALID_SPEC, or UNSUPPORTED")
        _require_non_empty("spec_path", self.spec_path)
        if self.operation_count < 0:
            raise ValueError("operation_count cannot be negative")
        if self.operation_count != len(self.operations):
            raise ValueError("operation_count must match the number of operations")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""
        return {
            "status": self.status,
            "spec_path": self.spec_path,
            "sha256": self.sha256,
            "openapi_version": self.openapi_version,
            "title": self.title,
            "api_version": self.api_version,
            "operation_count": self.operation_count,
            "operations": [
                {
                    "operation_id": operation.operation_id,
                    "method": operation.method,
                    "path": operation.path,
                    "response_codes": list(operation.response_codes),
                    "has_request_body": operation.has_request_body,
                    "required_inputs": list(operation.required_inputs),
                    "examples_available": operation.examples_available,
                }
                for operation in self.operations
            ],
            "errors": list(self.errors),
            "coverage_gaps": list(self.coverage_gaps),
            "unsupported_constructs": list(self.unsupported_constructs),
        }


def canonical_json_bytes(document: Mapping[str, object]) -> bytes:
    """Serialize a document to canonical UTF-8 JSON for hashing.

    Object keys are sorted; arrays are left in their original order because
    array ordering can be semantically meaningful. The result is stable across
    machines and Python runs.

    Args:
        document: Parsed JSON/YAML mapping.

    Returns:
        Canonical UTF-8 JSON bytes.
    """
    return json.dumps(
        dict(document),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    """Return the lowercase hexadecimal SHA-256 digest of ``data``."""
    return hashlib.sha256(data).hexdigest()


def _require_non_empty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _require_sha256(name: str, value: str) -> None:
    if not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase 64-character SHA-256 hex digest")


def _require_service_id(value: str) -> None:
    if not _SERVICE_ID_RE.fullmatch(value):
        raise ValueError("service_id must be a lowercase slug matching '^[a-z0-9][a-z0-9-]{0,62}$'")


def _require_http_url(name: str, value: str) -> None:
    _require_non_empty(name, value)
    try:
        parts = urlsplit(value)
    except ValueError as exc:
        raise ValueError(f"{name} is not a valid URL: {exc}") from exc
    if parts.scheme not in {"http", "https"}:
        raise ValueError(f"{name} must use http or https")
    if not parts.hostname:
        raise ValueError(f"{name} must include a host")
    if parts.username is not None or parts.password is not None:
        raise ValueError(f"{name} must not contain URL credentials")


def _require_utc(name: str, value: datetime) -> None:
    offset = value.utcoffset()
    if value.tzinfo is None or offset is None or offset != timedelta(0):
        raise ValueError(f"{name} must be timezone-aware UTC")
