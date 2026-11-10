"""Pure domain layer.

Contents:

- :mod:`contractguard.domain.models` — enums, immutable records, invariants, and
  canonical JSON/hash helpers.
- :mod:`contractguard.domain.ports` — protocols the service layer depends on.
- :mod:`contractguard.domain.errors` — typed expected failures.

Rules:

- Standard library only. No ``httpx``, ``yaml``, ``sqlite3``, ``openapi_core``,
  or Hermes imports.
- No network, filesystem, clock, or database access.
- Raise ``ValueError`` for broken invariants inside value objects; raise the
  appropriate :class:`~contractguard.domain.errors.ContractGuardError` subclass
  at service/adapter boundaries.
"""
