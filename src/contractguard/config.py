"""Immutable runtime configuration and hard safety constants.

Configuration is resolved from explicit mappings (tests) or ``CONTRACTGUARD_*``
environment variables (runtime). This module performs no I/O at import time and
does not import third-party or Hermes modules.

Safety-critical behaviour is deliberately **not** configurable in the MVP:

- live methods are GET/HEAD only;
- remote targets are disallowed;
- TLS verification stays enabled;
- redirects are never followed;
- environment proxy inheritance is disabled;
- retries and concurrency are disabled.

The HTTP adapter must enforce these constants even if a caller supplies
conflicting arguments.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

PLUGIN_NAME = "contractguard"
ENV_PREFIX = "CONTRACTGUARD_"

_KIB = 1024
_MIB = 1024 * _KIB

# ---------------------------------------------------------------------------
# Hard safety constants (not environment-tunable)
# ---------------------------------------------------------------------------

#: The only HTTP methods the MVP may dispatch to a live target.
LIVE_METHODS: frozenset[str] = frozenset({"GET", "HEAD"})

#: Remote targets require a reviewed SSRF/allowlist design (P1). Keep disabled.
ALLOW_REMOTE_TARGETS = False

#: Redirects are never followed; a 3xx response is reported as-is.
FOLLOW_REDIRECTS = False

#: Certificate verification is always enabled. Never add a verify=False escape.
VERIFY_TLS = True

#: Do not inherit proxy settings from the environment for deterministic runs.
TRUST_ENV = False

#: Absolute maximum number of live operations in a single call.
MAX_OPERATIONS_LIMIT = 5

#: Absolute maximum per-request timeout, in seconds.
MAX_TIMEOUT_SECONDS = 30.0

#: Absolute maximum number of history records returned in one call.
MAX_HISTORY_LIMIT = 20

# ---------------------------------------------------------------------------
# Defaults and validation bounds
# ---------------------------------------------------------------------------

DEFAULT_MAX_SPEC_BYTES = 2 * _MIB
DEFAULT_MAX_REQUEST_BODY_BYTES = 256 * _KIB
DEFAULT_MAX_RESPONSE_BYTES = 1 * _MIB
DEFAULT_HTTP_TIMEOUT_SECONDS = 5.0
DEFAULT_MAX_OPERATIONS_PER_RUN = 1
DEFAULT_MAX_HISTORY_RECORDS = 10

_MIN_SPEC_BYTES = 1 * _KIB
_MAX_SPEC_BYTES = 16 * _MIB
_MIN_REQUEST_BODY_BYTES = 1 * _KIB
_MAX_REQUEST_BODY_BYTES = 4 * _MIB
_MIN_RESPONSE_BYTES = 1 * _KIB
_MAX_RESPONSE_BYTES = 8 * _MIB
_MIN_TIMEOUT_SECONDS = 0.1


class ConfigurationError(ValueError):
    """Raised when a configuration value is missing, malformed, or unsafe.

    This is a boot-time error, distinct from a contract verdict. Plugin code
    must fail closed rather than silently substitute an unsafe default.
    """


@dataclass(frozen=True, slots=True)
class Settings:
    """Validated, immutable settings for one ContractGuard invocation.

    Attributes:
        max_spec_bytes: Maximum OpenAPI document size accepted from disk.
        max_request_body_bytes: Maximum serialized body used in offline
            preflight.
        max_response_bytes: Maximum number of response bytes read from a live
            target before the read is stopped.
        http_timeout_seconds: Total per-request budget.
        max_operations_per_run: Number of operations a single live test may
            execute.
        max_history_records: Default page size for history queries.
    """

    max_spec_bytes: int = DEFAULT_MAX_SPEC_BYTES
    max_request_body_bytes: int = DEFAULT_MAX_REQUEST_BODY_BYTES
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES
    http_timeout_seconds: float = DEFAULT_HTTP_TIMEOUT_SECONDS
    max_operations_per_run: int = DEFAULT_MAX_OPERATIONS_PER_RUN
    max_history_records: int = DEFAULT_MAX_HISTORY_RECORDS

    def __post_init__(self) -> None:
        """Validate all bounds and fail closed on unsafe values.

        Raises:
            ConfigurationError: If any value falls outside its permitted range.
        """
        _check_range(
            "max_spec_bytes",
            self.max_spec_bytes,
            _MIN_SPEC_BYTES,
            _MAX_SPEC_BYTES,
        )
        _check_range(
            "max_request_body_bytes",
            self.max_request_body_bytes,
            _MIN_REQUEST_BODY_BYTES,
            _MAX_REQUEST_BODY_BYTES,
        )
        _check_range(
            "max_response_bytes",
            self.max_response_bytes,
            _MIN_RESPONSE_BYTES,
            _MAX_RESPONSE_BYTES,
        )
        _check_range(
            "http_timeout_seconds",
            self.http_timeout_seconds,
            _MIN_TIMEOUT_SECONDS,
            MAX_TIMEOUT_SECONDS,
        )
        _check_range(
            "max_operations_per_run",
            self.max_operations_per_run,
            1,
            MAX_OPERATIONS_LIMIT,
        )
        _check_range(
            "max_history_records",
            self.max_history_records,
            1,
            MAX_HISTORY_LIMIT,
        )

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        """Build settings from ``CONTRACTGUARD_*`` environment variables.

        Missing or empty variables keep their defaults. Malformed values raise
        :class:`ConfigurationError` instead of being coerced.

        Args:
            env: Optional mapping to read instead of ``os.environ``. Tests use
                this to avoid mutating process state.

        Returns:
            A validated :class:`Settings` instance.

        Raises:
            ConfigurationError: If a supplied value cannot be parsed or is out
                of bounds.
        """
        source: Mapping[str, str] = os.environ if env is None else env
        return cls(
            max_spec_bytes=_env_int(source, "MAX_SPEC_BYTES", DEFAULT_MAX_SPEC_BYTES),
            max_request_body_bytes=_env_int(
                source,
                "MAX_REQUEST_BODY_BYTES",
                DEFAULT_MAX_REQUEST_BODY_BYTES,
            ),
            max_response_bytes=_env_int(
                source,
                "MAX_RESPONSE_BYTES",
                DEFAULT_MAX_RESPONSE_BYTES,
            ),
            http_timeout_seconds=_env_float(
                source,
                "HTTP_TIMEOUT_SECONDS",
                DEFAULT_HTTP_TIMEOUT_SECONDS,
            ),
            max_operations_per_run=_env_int(
                source,
                "MAX_OPERATIONS_PER_RUN",
                DEFAULT_MAX_OPERATIONS_PER_RUN,
            ),
            max_history_records=_env_int(
                source,
                "MAX_HISTORY_RECORDS",
                DEFAULT_MAX_HISTORY_RECORDS,
            ),
        )


def _env_int(env: Mapping[str, str], name: str, default: int) -> int:
    """Read an integer environment value with strict parsing."""
    key = f"{ENV_PREFIX}{name}"
    raw = env.get(key)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise ConfigurationError(f"{key} must be an integer, got {raw!r}") from exc


def _env_float(env: Mapping[str, str], name: str, default: float) -> float:
    """Read a floating-point environment value with strict parsing."""
    key = f"{ENV_PREFIX}{name}"
    raw = env.get(key)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw.strip())
    except ValueError as exc:
        raise ConfigurationError(f"{key} must be a number, got {raw!r}") from exc


def _check_range(name: str, value: float, minimum: float, maximum: float) -> None:
    """Raise when ``value`` falls outside the inclusive range."""
    if not minimum <= value <= maximum:
        raise ConfigurationError(f"{name} must be between {minimum} and {maximum}, got {value}")
