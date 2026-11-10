"""Use-case orchestration layer.

Planned services (implemented one slice at a time):

``inspect``
    Load and validate an OpenAPI document; build the operation inventory.
``preflight``
    Validate a proposed request offline; always report ``request_sent: false``.
``live_test``
    Resolve one registered operation, enforce policy, execute a bounded
    GET/HEAD request, and validate the actual response.
``diff``
    Compare a candidate snapshot with the stored baseline using an explicit,
    versioned ruleset.
``promote``
    Verify the exact candidate hash and delegate an atomic, compare-and-swap
    promotion to the baseline repository.
``history``
    Return bounded, redacted evidence receipts.

Rules:

- Depend on ``contractguard.domain`` only, plus the standard library.
- Receive adapters as arguments typed as ports (``domain.ports``); never import
  concrete adapters.
- Never perform network or database I/O directly.
- Do not report ``PASS`` when any required check was skipped or unsupported.
"""
