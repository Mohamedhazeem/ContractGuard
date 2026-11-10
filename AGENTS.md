# AGENTS.md — Rules for AI coding agents working on ContractGuard

This repository is a **native Hermes Agent plugin**. It validates HTTP API
requests and responses against OpenAPI documents, records reproducible evidence,
and compares candidate contracts with human-approved baselines.

Read this file before changing code. If an instruction here conflicts with a
one-off request, stop and ask the human. The rules below are not stylistic
preferences; several of them are safety and correctness requirements.

---

## 1. Source of truth, scope, and current stage

- **Product specification:** `docs/plan/ContractGuard_Project_Spec.md`.
  It defines verdicts, finding codes, tool contracts, safety policy, and the
  data model. Treat it as authoritative.
- **Delivery order:** `docs/plan/ContractGuard_Implementation.md`.
  Implement one slice at a time. Do not start the next slice until the current
  slice's acceptance tests pass.
- **Architecture decisions:** `docs/adr/`. Read the ADRs before changing
  validation, storage, or execution behaviour.
- **Current stage:** Stage 0 — scaffold. `plugin.yaml` declares no tools or hooks
  and `register(ctx)` registers nothing. This is intentional. Do not invent tool
  implementations to "fill out" the scaffold.

### Non-negotiable outcomes

1. A schema violation is `FAIL`; a missing input that prevented execution is
   `INCOMPLETE`; a blocked safety policy is `BLOCKED`; an invalid document is
   `INVALID_SPEC`. Never turn any of these into `PASS`.
2. Preflight never sends HTTP traffic and always reports `request_sent: false`.
3. The MVP never dispatches POST, PUT, PATCH, or DELETE.
4. Baselines are immutable, content-addressed, and promoted only after explicit
   human approval.
5. A partial test run is never reported as a clean `PASS`.

---

## 2. Layering and dependency rules

```
┌──────────────────────────────────────────────────────────────┐
│ Hermes Agent                                                 │
│   ctx.register_tool(...)  ctx.register_hook(...)             │
└───────────────────────────┬──────────────────────────────────┘
                            │ documented plugin API only
┌───────────────────────────▼──────────────────────────────────┐
│ tools/ + hooks/          thin Hermes-facing adapters          │
│   arg validation · JSON envelopes · approval gate · nudges    │
└───────────────────────────┬──────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────┐
│ services/                use-case orchestration               │
│   inspect · preflight · live test · diff · promote · history   │
└───────────────┬──────────────────────────────┬───────────────┘
                │ depends on                   │ depends on
┌───────────────▼──────────────┐  ┌────────────▼───────────────┐
│ domain/                      │  │ adapters/                  │
│ pure types, rules, ports     │  │ SQLite · HTTPX · openapi-  │
│ stdlib only; no I/O          │  │ core · YAML · Hermes glue  │
└──────────────────────────────┘  └────────────────────────────┘
```

The arrow of dependency always points **inward**:

- `domain/` imports only the Python standard library. It must never import
  `openapi_core`, `httpx`, `yaml`, `sqlite3`, or any Hermes module.
- `services/` may import `domain/` and Python stdlib. It receives adapters
  through constructor injection or function arguments typed as ports. It must
  not import concrete adapter modules.
- `adapters/` may import `domain/`, third-party libraries, and documented Hermes
  helpers. Adapters translate external data into domain types and never leak
  library objects (HTTPX responses, sqlite rows, `openapi-core` errors) upward.
- `tools/` and `hooks/` are composition roots. They may import services and
  adapters, but they must stay thin: parse arguments, call one use case,
  serialize the result.
- `config.py` is dependency-free apart from the stdlib. It must not read files
  or open connections at import time.

### SOLID rules in practice

- **Single responsibility:** one module owns one concern. Do not add a helper
  to `config.py` merely because it is convenient.
- **Open/closed:** extend compatibility rules by adding registered rule objects,
  not by growing a single `if/elif` chain.
- **Liskov:** adapter implementations must satisfy the protocols in
  `domain/ports.py` without narrowing behaviour or raising undocumented errors.
- **Interface segregation:** prefer small, purpose-built protocols over one
  large "god" port.
- **Dependency inversion:** services depend on ports; the composition root
  supplies concrete adapters.

If a change requires a new cross-layer dependency, write an ADR first.

---

## 3. Repository map

| Path | Responsibility | May import |
|---|---|---|
| `plugin.yaml` | Hermes manifest; must match registration exactly | n/a |
| `__init__.py` (root) | Thin Hermes bootstrap and `register(ctx)` re-export | stdlib, `contractguard` |
| `src/contractguard/config.py` | Immutable settings, env parsing, hard safety constants | stdlib |
| `src/contractguard/domain/` | Enums, value objects, invariants, ports, domain errors | stdlib |
| `src/contractguard/services/` | Use cases and orchestration | stdlib, domain |
| `src/contractguard/adapters/` | SQLite, HTTPX, openapi-core, YAML, Hermes storage | stdlib, domain, third-party, documented Hermes helpers |
| `src/contractguard/tools/` | Tool JSON schemas and handlers | stdlib, domain, services, adapters |
| `src/contractguard/hooks/` | `pre_tool_call`, `pre_verify` callbacks | stdlib, domain, services |
| `tests/unit/` | Pure, fast, no network, no sleeping | anything under test |
| `tests/integration/` | Adapters, local HTTP fixture, SQLite integration | anything under test |
| `tests/fixtures/` | OpenAPI documents and mock API assets | n/a |
| `demo/` | FastAPI fixture for the recorded workflow | n/a |

Never write runtime state into this repository or into the installed plugin
directory. Runtime state belongs in Hermes-managed storage:
`plugin_data_dir("contractguard")` / `plugin_db("contractguard")`.

---

## 4. Hermes constraints (hard boundaries)

- **Never patch or wrap Hermes core.** Do not assign to `AIAgent` methods, call
  `setattr` on Hermes modules, replace module attributes, write into
  `sys.modules`, or import private internals. The plugin catalog rejects these
  patterns, and they break on every Hermes upgrade.
- Use **only documented `ctx.*` APIs**: `ctx.register_tool`,
  `ctx.register_hook`, `ctx.get_config`, and other methods documented in the
  official plugin guide.
- Storage uses the documented helper import:
  `from plugins.plugin_storage import plugin_data_dir, plugin_db`.
  Resolve it lazily inside the adapter, not at plugin import time.
- Handler signature is exactly `def handler(args: dict[str, Any], **kwargs) -> str`.
  Always accept `**kwargs`. Always return a JSON string, including on failure.
- Hook callbacks accept `**kwargs` so additive Hermes payload fields do not
  break them. Never rely on positional arguments.
- `plugin.yaml` must list every registered tool and hook. If a tool is cut,
  remove it from both `register()` and the manifest in the same commit.
- Keep registration synchronous and fast. No network, no subprocesses, no file
  scans, no database migrations during `register(ctx)`.
- Do not add a Desktop UI, gateway adapter, or background service. The plugin's
  surface is tools, two hooks, and plugin storage.
- `hermes plugins doctor .` and `hermes plugins validate . --install-deps` must
  pass before release. Doctor runs registration in a clean temporary home.

If a needed public seam does not exist, stop and report it. Do not reach into
private modules.

---

## 5. Coding standards

### Python and typing

- Target Python 3.10. Do not use 3.11+ only syntax (`StrEnum`, `Self`,
  `ExceptionGroup`, `type` aliases, `tomllib` as a runtime import).
- Every module, public class, public function, and tool handler has a docstring.
  Use Google-style docstrings; document `Args`, `Returns`, `Raises` where useful.
- All function signatures, including tests where practical, are fully typed.
  `mypy --strict` must pass for `src/`.
- Use `from __future__ import annotations` in every Python module.
- Prefer immutable value objects (`@dataclass(frozen=True, slots=True)`) in the
  domain. Do not mutate inputs.
- Use `collections.abc` types (`Mapping`, `Sequence`) for read-only parameters.
- Use `pathlib.Path`, not string path concatenation.
- Catch the narrowest exception that can be handled. Never use bare `except:`.

### Style and structure

- Ruff is the formatter/linter: 100-character lines, import sorting enabled.
- No `print()` in plugin code. Use module-level `logging.getLogger(__name__)`.
- No mutable module-level state. The compatibility ruleset is the one allowed
  exception, and it must be an immutable tuple built once.
- No hidden I/O in constructors. Adapters expose explicit methods.
- Keep functions small and return early. Avoid deep nesting.
- Public JSON field names are a contract. Do not rename them without a versioned
  change and an ADR.

### Error handling

- Raise typed domain errors (`domain/errors.py`) internally. Do not raise bare
  `Exception` or `RuntimeError` for expected failures.
- Tool handlers are a boundary: they must catch expected failures and return a
  structured JSON envelope. Ordinary validation, storage, parse, and network
  errors must not escape as uncaught exceptions.
- Never include a traceback in an agent-facing result. Log diagnostics locally
  with secrets redacted.
- Distinguish transport failure (`INCOMPLETE`/`BLOCKED`) from schema violation
  (`FAIL`). A refused connection is not a contract failure.
- Database errors must preserve existing data. Never "fix" a storage problem by
  deleting or recreating the database.

### Time, hashes, and canonical data

- Timestamps are timezone-aware UTC ISO-8601 strings.
- Spec hashes are lowercase SHA-256 hex over canonical JSON bytes:
  `json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`.
  Do not sort arrays; array order can be semantically meaningful.
- Never identify a baseline by file path. Store normalized JSON plus the hash.
- Use `yaml.safe_load` only. Never `yaml.load`, `yaml.full_load`, or custom
  constructors.
- Reject external `$ref` values. Do not fetch remote references.

---

## 6. Security and safety rules

These apply to every contribution, including tests and demos.

### Network

- Live targets are loopback only (`localhost`, `127.0.0.1`, `::1`) in the MVP.
  Enforce the resolved address, not just the hostname string.
- Live execution is limited to `GET` and `HEAD`. Write methods must return
  `BLOCKED` with `request_sent: false`.
- `follow_redirects=False`, `verify=True`, `trust_env=False`.
- Explicit timeouts (default 5 s) and a bounded streaming response reader
  (default 1 MiB). Stop reading at the cap.
- No retries, no concurrent live requests, no background requests.
- Never take a target URL from a spec's `servers` block without an explicit
  registered service and policy check.
- Reject URLs containing user information (`user:pass@host`) and non-HTTP(S)
  schemes.

### Secrets and evidence

- Reject `Authorization`, `Cookie`, `Set-Cookie`, `Proxy-Authorization`, and
  API-key headers from model-supplied tool arguments.
- Redact secret-bearing headers from logs, findings, history, and errors.
- Do not persist full request or response bodies. Persist type names, JSON
  Pointers, status codes, sizes, and durations.
- Do not scan `.env` files or auto-load credentials.
- Any new field written to SQLite must be reviewed for secret leakage.

### Filesystem

- Read only the exact spec path supplied by the user. Enforce the size cap
  before parsing.
- Do not write into the plugin installation directory.
- Do not edit API source code; that is Hermes' job through its normal tools.

---

## 7. Testing rules

**Never commit without a passing test suite.** A change is not done because it
"looks right" or because Hermes returned a plausible sentence.

Required before every commit:

```bash
pytest
ruff check .
ruff format --check .
mypy
```

### Test placement and expectations

- `tests/unit/`: pure domain and service logic. No network, no real clock, no
  sleeps, no filesystem writes outside `tmp_path`. Fast enough to run on save.
- `tests/integration/`: adapters against in-memory SQLite, local ASGI/HTTP
  fixtures, and real `openapi-core` validation. Mark them `@pytest.mark.integration`.
- Any test that needs a listening socket is also marked `@pytest.mark.network`
  and must bind to loopback on an ephemeral port.
- Use the fixtures in `tests/conftest.py`. Do not duplicate the OpenAPI fixture;
  extend `tests/fixtures/openapi/giftshop.yaml` when a new shape is needed.
- Every fixed defect gets a regression test with the exact finding code and JSON
  Pointer.
- Every compatibility rule gets at least one fixture-based test for breaking,
  non-breaking, and unclassified outcomes.
- Security tests are mandatory for new request paths: blocked method, non-loopback
  target, redirect, oversized response, secret header, and missing input.

### Truthfulness of tests

- Do not mock the validator when the test claims to prove validation. Adapter
  unit tests may use fakes; end-to-end claims require the real adapter.
- Do not assert only that a function "does not crash". Assert the verdict,
  finding code, pointer, and `request_sent` value.
- Do not weaken an assertion to make a failing build green. Fix the code or
  document the limitation and change the expected verdict to `INCOMPLETE`.
- Tests must not depend on execution order or shared mutable module state.

---

## 8. Change workflow

1. Read the relevant spec section, implementation slice, and ADR.
2. Write or update the failing test first.
3. Implement the smallest change that satisfies the layer boundary.
4. Run the full local gate (`pytest`, `ruff`, `mypy`).
5. Update `plugin.yaml` if registration changed.
6. Update documentation and add an ADR for any architectural decision.
7. Update `README.md` if setup, behaviour, or limitations changed.

### Definition of done

- [ ] Behaviour matches the spec's verdict and finding-code semantics.
- [ ] Layer boundaries are intact; no new reverse dependency.
- [ ] Public functions and tools have docstrings and type hints.
- [ ] Failure paths return structured JSON, not tracebacks.
- [ ] Secrets and bodies are not persisted or logged.
- [ ] Tests cover the happy path, the failure path, and one boundary case.
- [ ] `pytest`, `ruff`, and `mypy` pass locally.
- [ ] `plugin.yaml` matches `register(ctx)`.
- [ ] Docs/ADR updated; no stale claims about capability.

### Forbidden shortcuts

- Do not add a dependency without a bounded version range and a reason.
- Do not call a partial or skipped run `PASS`.
- Do not make baseline promotion implicit.
- Do not add async/background execution "for performance" (see ADR-003).
- Do not replace a proven validator with a hand-rolled schema check silently.
- Do not change a finding code after release without a documented migration.
- Do not commit credentials, private specs, or captured production traffic.
