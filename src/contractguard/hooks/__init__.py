"""Hermes lifecycle hooks.

``pre_tool_call``
    Gate only ``contractguard_promote_baseline`` behind human approval. Return
    ``{"action": "approve", "message": ...}``; never gate inspection, preflight,
    or read-only live checks. Hermes fails closed when the approval gate is
    unavailable.

``pre_verify``
    Optional, one-shot nudge after API/spec files were edited. Return
    ``{"action": "continue", "message": ...}`` only when ``coding`` is true,
    ``attempt == 0``, and changed paths match the configured patterns. Never
    perform network I/O inside the hook; ask Hermes to call the tool instead.

Rules:

- Accept ``**kwargs`` so additive Hermes payload fields do not break the hook.
- Never patch or wrap Hermes core behaviour.
- Hooks must be fast, idempotent, and safe to invoke concurrently.
"""
