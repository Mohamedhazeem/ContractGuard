# Changelog

All notable changes to ContractGuard are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] — 2026-11-11

### Added

- `contractguard_history` — returns bounded, redacted evidence receipts for a
  registered service.
- Evidence persistence: `contractguard_validate_request`, `contractguard_test`,
  and `contractguard_diff` now record a receipt (verdict, spec hash, operation,
  duration, coverage, finding IDs) in the Hermes plugin database.
- `SECURITY.md` — threat model, safety boundaries, and disclosure.
- GitHub Actions workflow running the quality gate and both Hermes plugin
  validation commands, with a 3-day dependency release-age quarantine.

### Fixed

- Dependency floor corrected: `openapi-spec-validator>=0.8.5` (was `>=0.8`).
  Versions 0.8.0 and 0.8.1 lack `OpenAPIV32SpecValidator`, which
  `openapi-core>=0.23` imports at module load, so the previous floor allowed an
  install that crashed on import. 0.8.5 is also the first release accepting the
  `jsonschema>=4.25` line Hermes pins.
- `openapi-core` floor documented as `>=0.23`: 0.21 and 0.22 reject OpenAPI 3.2
  documents as "spec not detected".

### Changed

- `requires_hermes: ">=0.21.6"` declared in `plugin.yaml`, matching the first
  Hermes release that ships the `pre_verify` hook, the plugin storage helpers,
  and manifest-level `requires_hermes` support.
- Manifest metadata added: `author`, `homepage`, `tags`.
- README restructured for catalog review: product problem, feature list,
  one-shot setup prompt, usage guides, judge-facing verification, and an
  explicit disclosure section.

## [0.1.0] — 2026-11-10

### Added

- Native Hermes plugin skeleton with `register(ctx)` and `plugin.yaml`.
- `contractguard_ping` health-check tool.
- Domain layer: verdicts, findings, immutable baselines, ports, and errors.
- SQLite storage primitives and the services, baselines, runs, and findings
  schema in Hermes plugin storage.
- OpenAPI-core request/response adapters with casting disabled, proven by the
  Slice 0 adapter spike.
- Architecture Decision Records for validation engine, baseline storage, and
  synchronous execution.

[0.2.0]: https://github.com/Mohamedhazeem/ContractGuard/releases/tag/v0.2.0
[0.1.0]: https://github.com/Mohamedhazeem/ContractGuard/releases/tag/v0.1.0
