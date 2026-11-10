# ADR-003: Execute all tools synchronously with hard bounds

- **Status:** Accepted
- **Date:** 2026-11-10
- **Deciders:** ContractGuard maintainers
- **Related:** [Product specification, §8 and §14](../plan/ContractGuard_Project_Spec.md),
  [Implementation slices 4–6](../plan/ContractGuard_Implementation.md),
  [ADR-001](001-use-openapi-core.md), [ADR-002](002-immutable-baselines.md)

## Context

Hermes tool handlers are synchronous request/response functions: they receive
arguments, perform work, and return a JSON string. Hermes uses the return value
immediately to continue the agent turn. There is no documented contract for a
handler to enqueue work and later push a result back into the conversation.

ContractGuard's work is deliberately small and bounded:

- parse and validate one local OpenAPI document;
- validate one proposed request offline;
- perform at most a handful of loopback GET/HEAD requests;
- diff two in-memory documents;
- write one short SQLite transaction.

None of these is a batch job. A background worker would add a queue, a process
or thread lifecycle, result retrieval, cancellation, crash recovery, and a new
security surface (unattended network access) for no user-visible benefit.

The hackathon demo also depends on determinism. The agent must see a failure,
edit code, re-run the same operation, and see `PASS` in the same turn. Asynchronous
jobs introduce polling, stale results, and ordering ambiguity that make the
repair loop harder to explain and easier to break.

Finally, live HTTP execution is the most safety-sensitive operation in the
plugin. A synchronous call with explicit timeouts and byte caps is easy to
audit: the request starts and finishes inside one handler invocation, and the
verdict is returned with the evidence.

## Decision

All ContractGuard operations execute **synchronously inside the tool handler**.
There are no background workers, no task queues, no daemon threads, and no
fire-and-forget requests.

Hard bounds:

- One live operation per call by default; absolute maximum five.
- Total per-request budget defaults to 5 seconds, hard maximum 30 seconds.
- Response bodies are read through a streaming cap (default 1 MiB) and the read
  stops at the cap.
- No automatic retries. No concurrent live requests.
- SQLite writes are short, explicit transactions. Promotion uses compare-and-swap
  (ADR-002).
- A timeout or transport failure returns `INCOMPLETE`; a policy refusal returns
  `BLOCKED`; neither is retried in the background.
- Hooks must remain fast and side-effect free with respect to the network. The
  `pre_verify` hook may *ask* Hermes to run a check; it must not execute a live
  request inside the hook callback.

The only deferred work permitted is the agent's own next turn (for example, the
`pre_verify` nudge returning `{"action": "continue", ...}`), which Hermes owns
and bounds with `agent.max_verify_nudges`.

## Consequences

### Positive

- Deterministic, easy-to-explain behaviour: one call, one verdict, one receipt.
- Latency is bounded and visible; a hung target cannot hold an unbounded worker.
- Failure semantics are unambiguous and returned in the same response.
- No new process, queue, or lifecycle code to secure and test.
- SQLite concurrency remains manageable with WAL and short transactions.
- The demo's broken → repair → pass loop runs in one agent session.

### Negative

- A slow API consumes the tool call's wall-clock budget. That is intentional;
  the caller receives `INCOMPLETE` rather than an invisible pending job.
- The plugin cannot run large test matrices or property-based campaigns. Those
  belong to a future batch/CI integration or a separate engine.
- Multiple concurrent agent sessions can contend on SQLite writes. Mitigated by
  WAL, short transactions, and compare-and-swap promotion; true parallel
  baseline promotion is rejected as stale.
- The UI cannot show progressive results. Tool results are complete snapshots,
  which is the correct trade-off for evidence-based verification.
- Very large OpenAPI documents may need more parsing time; the 2 MiB cap keeps
  this bounded.

### Revisit criteria

Revisit this decision only if all of the following become true:

1. Hermes documents a supported asynchronous job surface with result delivery;
2. batch verification across many services becomes a primary use case;
3. the safety model for unattended network access has an approved design;
4. synchronous completion demonstrably harms the agent loop.

Until then, a background implementation is out of scope.

## Alternatives considered

### `asyncio` tasks created by the handler

Rejected. Hermes expects a return value; an orphaned task has no owner, no
cancellation path, and no way to attach its result to the turn. It also makes
shutdown and exception reporting unreliable.

### A thread pool

Rejected. It adds concurrency to the HTTP and SQLite paths, complicates timeout
enforcement (Python threads cannot be forcibly cancelled), and provides no
benefit for single-operation checks.

### An external queue or worker (Celery, RQ, a subprocess daemon)

Rejected. It introduces a service to install, monitor, and secure, plus result
storage and polling. This is disproportionate for a plugin that must remain
in-process and easy to validate in a clean Hermes home.

### Long-running property-based testing in the handler

Rejected for the MVP. Schemathesis-style generation is explicitly a post-MVP
engine. The first release proves deterministic, selected-operation verification,
not fuzzing.

## References

- Hermes plugin guide: tool handler conventions and `ctx.register_tool`.
- ContractGuard product specification, sections 8.1, 8.4, and 14.
- ContractGuard implementation plan, slices 4–6 and risk register.
- SQLite WAL documentation: <https://www.sqlite.org/wal.html>
