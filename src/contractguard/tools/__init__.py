"""Hermes-facing tool layer.

Every tool handler will follow the documented shape::

    def handler(args: dict[str, Any], **kwargs: Any) -> str:
        ...

Rules:

- Return a JSON string for success **and** failure. Never raise ordinary parse,
  validation, storage, or network errors through the handler.
- Reject unexpected arguments explicitly.
- Keep handlers thin: validate arguments, invoke one service, serialize the
  result. Business logic belongs in ``services/``.
- Tool JSON schemas are what the model reads. Their descriptions must state what
  the tool does, what it does not do, and its safety boundary (for example,
  preflight never sends the request).
- Registration names use the ``contractguard_`` namespace and must match
  ``plugin.yaml`` exactly.
"""
