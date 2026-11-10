# ADR-001: Use openapi-core for runtime contract validation

- **Status:** Accepted
- **Date:** 2026-11-10
- **Deciders:** ContractGuard maintainers
- **Related:** [Product specification, §10](../plan/ContractGuard_Project_Spec.md),
  [Implementation slice 0](../plan/ContractGuard_Implementation.md),
  [ADR-003](003-synchronous-execution.md)

## Context

ContractGuard must answer two different runtime questions:

1. Would a proposed request conform to the operation's declared parameters,
   media type, and body schema?
2. Does an actual HTTP response conform to the response declared for its status
   code and media type?

The validator must handle OpenAPI 3.0.x, 3.1.x, and 3.2.x without us maintaining
three schema dialects. It must also report machine-readable, field-level
findings so Hermes can repair the implementation rather than guess.

A hand-rolled validator is a large, deceptively difficult surface: `$ref`
resolution, `allOf`/`oneOf`/`anyOf`, nullable semantics, parameter serialization
styles, content-type selection, status-range matching (`2XX`, `default`), and
format handling. The product's differentiator is the agent workflow, not a new
JSON Schema engine. Validation correctness is the foundation that workflow
depends on.

We also need structural document validation with useful diagnostics before any
runtime validation occurs. `openapi-spec-validator` is purpose-built for that
step and is already an established companion in the Python OpenAPI ecosystem.

## Decision

Use **`openapi-core` as the single runtime request/response validation engine**
and **`openapi-spec-validator` for document-level validation and diagnostics**.

Specifically:

- Parse local JSON/YAML with `PyYAML` (`safe_load`) or `json`, enforce a size cap,
  reject external `$ref`, then validate the document structure.
- Build `openapi-core`'s `OpenAPI` object from the in-memory document. Do not
  use its file path adapter as the trust boundary.
- Implement two thin adapter classes in `adapters/`:
  - a **request adapter** exposing the protocol properties `host_url`, `path`,
    `full_url_pattern`, `method`, `parameters`, `body`, and `content_type`;
  - a **response adapter** exposing `status_code`, `headers`, `content_type`,
    and `data`.
- Translate `openapi-core` validation errors into ContractGuard's own
  `Finding` value objects. No `openapi-core` exception or object may cross into
  `domain/` or `services/`.
- Pin exact versions after the Slice 0 compatibility spike. Do not ship
  floating "latest" ranges.

The adapters are the only modules allowed to import `openapi_core`. The domain
and services layers depend on the protocols in `domain/ports.py`.

## Consequences

### Positive

- One maintained engine covers the three target OpenAPI versions instead of a
  bespoke dialect layer.
- Request and response validation share schema semantics, reducing drift between
  preflight and live verification.
- Field-level errors can be normalized into stable ContractGuard finding codes
  with JSON Pointers.
- `openapi-spec-validator` gives structural findings before runtime validation,
  so an invalid document becomes `INVALID_SPEC` rather than a confusing runtime
  failure.

### Negative

- `openapi-core` expects its own request/response protocol objects. The HTTPX
  response cannot be passed through unchanged, so an adapter layer must be
  proven early. This is the highest technical risk in the project.
- Validation error shapes are a dependency surface. A library upgrade can change
  messages or error classes; the normalization layer must have fixture tests.
- `openapi-core` performs spec validation and may be stricter than the demo
  expects. Some valid-but-unusual constructs may need to be reported as
  `INCOMPLETE` rather than silently accepted.
- The dependency tree is non-trivial for a plugin; versions must be bounded and
  tested inside Hermes' Python environment.

### Mitigation

Slice 0 is a **GO/NO-GO gate**. Before feature work proceeds, the spike must:

1. validate an intentionally invalid request body through the request adapter;
2. validate a real HTTPX response through the response adapter and produce a
   field-level type mismatch;
3. confirm external `$ref` is never fetched;
4. record resolved package versions and the Python version.

If the adapter cannot be made reliable within the spike budget, fall back to
`openapi-schema-validator` plus narrowly scoped manual parameter/status checks.
The fallback must be documented and must report unsupported semantics as
`INCOMPLETE`; it must not be presented as equivalent coverage.

## Alternatives considered

### Custom validation on top of `jsonschema`

Rejected. It duplicates years of OpenAPI-specific semantics (parameter styles,
content negotiation, status matching, `$ref` handling) and would make the
validator itself the product risk. The demo would pass while real-world specs
quietly fail.

### `openapi-schema-validator` plus manual request/parameter logic

Viable only as the documented fallback. It reduces adapter complexity but
requires hand-written handling for path/query/header serialization and response
status selection, which is exactly where silent false negatives occur.

### Schemathesis as the validation engine

Rejected for the MVP. Schemathesis is a strong property-based testing engine, but
it generates and executes tests, brings heavier dependencies, and is not the
right primitive for "validate this specific request without sending it" or
"validate this already-received response." It remains a possible P2 engine.

### A proxy or traffic-inspection tool such as Wiretap

Rejected. ContractGuard is not a proxy. A proxy cannot provide offline request
preflight or the agent's repair-and-repeat loop, and it adds a long-running
process to a plugin that must remain in-process and synchronous.

## References

- [openapi-core](https://github.com/python-openapi/openapi-core) — request and
  response validation for OpenAPI 3.0, 3.1, and 3.2.
- [openapi-core protocol reference](https://openapi-core.readthedocs.io/en/latest/reference/protocols/)
- [openapi-spec-validator](https://pypi.org/project/openapi-spec-validator/)
- [OpenAPI Specification 3.2.1](https://spec.openapis.org/oas/v3.2.1.html)
- ContractGuard product specification, sections 10 and 11.
