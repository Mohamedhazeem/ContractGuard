"""Concrete I/O adapters.

Planned adapters:

``sqlite``
    Schema, connection factory, and repositories for services, baselines, runs,
    and findings.
``spec_loader``
    Bounded JSON/YAML loading, ``openapi-spec-validator`` diagnostics, external
    ``$ref`` rejection, and operation indexing.
``validator``
    ``openapi-core`` request/response adapters. The only modules allowed to
    import ``openapi_core``.
``http_transport``
    HTTPX execution with loopback-only policy, GET/HEAD enforcement, timeouts,
    redirect refusal, and a bounded streaming reader.
``hermes_storage``
    Lazy wrappers around documented Hermes helpers:
    ``plugins.plugin_storage.plugin_data_dir`` and ``plugin_db``.

Rules:

- Translate library objects and exceptions into domain types at this boundary.
- Never leak HTTPX responses, sqlite rows, or ``openapi-core`` errors upward.
- Resolve Hermes imports lazily so unit tests and packaging do not require a
  Hermes installation at import time.
"""
