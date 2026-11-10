"""Typed domain errors.

Services and adapters raise these errors for expected failures. Hermes tool
handlers catch them at the boundary and serialize a structured JSON envelope.
Ordinary validation, storage, and transport failures must never escape a tool
handler as an uncaught exception, and tracebacks must never reach the model.
"""

from __future__ import annotations

from collections.abc import Mapping


class ContractGuardError(Exception):
    """Base class for expected ContractGuard failures.

    Attributes:
        code: Stable machine-readable error code.
        message: Safe, human-readable description with no secrets.
        details: Optional structured context, already redacted.
    """

    code: str = "CONTRACTGUARD_ERROR"

    def __init__(
        self,
        message: str,
        *,
        details: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, object] = dict(details or {})

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation for a tool envelope."""
        payload: dict[str, object] = {"code": self.code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return payload


class SpecLoadError(ContractGuardError):
    """The document could not be read or parsed (missing, oversized, bad YAML)."""

    code = "SPEC_LOAD_ERROR"


class SpecValidationError(ContractGuardError):
    """The document parsed but is not a structurally valid OpenAPI document."""

    code = "INVALID_SPEC"


class PolicyError(ContractGuardError):
    """A safety policy refused the requested action."""

    code = "BLOCKED"


class IncompleteInputError(ContractGuardError):
    """Required user-supplied data was missing, so the check could not run."""

    code = "INCOMPLETE"


class NotFoundError(ContractGuardError):
    """A referenced service, baseline, operation, or run does not exist."""

    code = "NOT_FOUND"


class StorageError(ContractGuardError):
    """A persistence operation failed; existing data must be preserved."""

    code = "STORAGE_ERROR"
