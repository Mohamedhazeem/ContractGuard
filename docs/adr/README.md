# Architecture Decision Records

This directory records the decisions that shape ContractGuard's architecture.
An ADR is required for any change that introduces a new dependency, changes a
layer boundary, alters persistence or execution semantics, or changes a public
contract (tool schema, JSON field, finding code).

## Index

| ID | Title | Status | Date |
|---|---|---|---|
| [ADR-001](001-use-openapi-core.md) | Use openapi-core for runtime contract validation | Accepted | 2026-11-10 |
| [ADR-002](002-immutable-baselines.md) | Store immutable JSON baselines with SHA-256 in SQLite | Accepted | 2026-11-10 |
| [ADR-003](003-synchronous-execution.md) | Execute all tools synchronously with hard bounds | Accepted | 2026-11-10 |

## Format

Each record uses the following structure:

```markdown
# ADR-NNN: Title

- **Status:** Proposed | Accepted | Superseded by ADR-NNN | Deprecated
- **Date:** YYYY-MM-DD
- **Deciders:** who approved it
- **Related:** links to specs, issues, or other ADRs

## Context
What forces are at play? What constraint makes this decision necessary?

## Decision
What we will do, stated in the active voice.

## Consequences
Positive, negative, and neutral outcomes. Include operational and security
effects, not only code effects.

## Alternatives considered
What else was viable, and why was it rejected?

## References
Primary sources, documentation, and spike results.
```

## Rules

- ADRs are immutable once accepted. Correct a mistake with a new ADR that
  supersedes the old one; do not rewrite history.
- "Accepted" means the code may rely on it. "Proposed" means it is open for
  discussion and must not be treated as settled.
- Record the verification evidence (versions tested, spike outcome) in the ADR
  when the decision depends on a third-party library.
