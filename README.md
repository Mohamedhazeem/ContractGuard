# ContractGuard

**Evidence before you ship.**

ContractGuard is a native [Hermes Agent](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins)
plugin that proves an HTTP API still matches its OpenAPI contract. It validates
proposed requests before they are sent, verifies live responses even when the
status code is `200`, compares contract changes against an approved baseline, and
gives the agent precise, reproducible evidence to repair the implementation and
re-run the same check.

> HTTP 200 is not proof your API is correct.

---

## The problem

APIs fail their contracts in ways that ordinary smoke tests cannot see:

- A response returns `200 OK` but serializes a numeric `price` as the string
  `"49.99"`.
- A required response property disappears after a refactor.
- A previously optional request field becomes required.
- A request parameter changes type or loses accepted enum values.
- The OpenAPI document and the implementation drift apart for weeks.
- A candidate specification removes an endpoint that real clients still call.

A coding agent can read the code and claim the API "looks correct", but an agent
should not be the authority on schema validity. A `200` only proves that the
transport worked. It does not prove the request shape, response shape, status
code, media type, or compatibility promise were honoured.

Validation tools already exist, but they usually sit outside the agent's
implementation loop. The developer has to leave the conversation, export a
payload, run a separate tool, interpret a traceback, return to the editor, and
try again. The evidence is disconnected from the code change, and contract drift
is reviewed late or not at all.

## What ContractGuard solves

ContractGuard puts deterministic API verification directly inside the agent's
coding loop.

| Question | ContractGuard answer | Proof it returns |
|---|---|---|
| Is this OpenAPI document valid? | Document inspection | Version, parser findings, operation inventory |
| Would this request conform? | Offline request preflight | Every finding, plus `request_sent: false` |
| Does the running API conform? | Bounded live verification | Actual status, media type, response-schema findings |
| Is this contract change safe? | Baseline comparison | Breaking, potentially breaking, non-breaking, unclassified |
| What happened last time? | Evidence history | Redacted receipts with spec hash and run metadata |
| May this candidate become the reference? | Approval-gated promotion | Immutable, content-addressed baseline |

The result is a closed loop:

```text
proposed request ──► preflight ──► FAIL / PASS   (nothing is sent)
live API         ──► bounded GET/HEAD ──► response validation ──► evidence
candidate spec   ──► diff vs approved baseline ──► classified changes
human approval   ──► promote exact SHA-256 ──► new immutable baseline
agent            ──► read findings ──► fix code ──► repeat the same check
```

ContractGuard does not decide whether business logic is correct, generate a
replacement API, proxy production traffic, or approve contract changes on the
agent's behalf.

---

## Key features

### 1. Offline request preflight

Validate path, query, header, and JSON body inputs against the declared
operation. The tool is built so that a write payload can be checked without any
network dispatch. Every preflight result reports `request_sent: false`.

### 2. Live response verification

Execute a bounded `GET` or `HEAD` request against an explicitly registered
development target and validate the **actual** status, media type, headers, and
body against the matching response schema. A `200` with a wrong field type is a
`FAIL`, not a pass.

### 3. Immutable approved baselines

A baseline stores the normalized OpenAPI JSON and its SHA-256 digest in SQLite.
Editing `openapi.yaml` on disk cannot silently change what was approved.
Historical baselines remain available for comparison and audit.

### 4. Compatibility diff with an explicit unclassified bucket

Classify supported changes from the consumer's perspective: removed paths and
operations, removed response properties, newly required request inputs, stricter
constraints, incompatible type changes, and more. Complex or untested schema
constructs are reported as `unclassified` rather than guessed.

### 5. Human-approved promotion

Baseline promotion is routed through Hermes' human-approval gate. The tool
requires the exact candidate SHA-256, re-reads and re-hashes the file, and
promotes transactionally with compare-and-swap. No register, test, or diff
operation promotes implicitly.

### 6. Evidence receipts, not raw traffic

Each run records the spec hash, operation, method, status code, media type,
duration, response size, verdict, coverage counts, and finding pointers. Full
request and response bodies are not persisted by default, and secret-bearing
headers are rejected and redacted.

### 7. Safety by default

Live execution is limited to loopback targets and `GET`/`HEAD`. Redirects are
never followed, TLS verification stays enabled, proxy environment inheritance is
disabled, timeouts are enforced, and response reads stop at a byte cap. Write
methods are preflight-only.

### 8. Native, deterministic, and honest

ContractGuard uses documented Hermes plugin APIs only, never patches Hermes
core, and runs synchronously with hard bounds. Every result uses one of five
verdicts: `PASS`, `FAIL`, `BLOCKED`, `INCOMPLETE`, or `INVALID_SPEC`. A skipped,
unsupported, or partially covered run is never reported as a clean `PASS`.

---

## How it works

```text
Hermes Agent
    │  documented ctx.register_tool / ctx.register_hook
    ▼
tools/ + hooks/          argument validation, JSON envelopes, approval gate
    │
    ▼
services/                inspect · preflight · live test · diff · promote · history
    │            ┌──────────────────────────────────────────────┐
    │            │ adapters/                                    │
    │            │ SQLite · HTTPX · openapi-core · PyYAML       │
    │            └──────────────────┬───────────────────────────┘
    ▼                               │ implements ports
domain/  ◄──────────────────────────┘
pure types, invariants, protocols
```

- The **domain** layer holds verdicts, immutable records, invariants, and the
  ports that define every external boundary. It has no I/O.
- **Services** orchestrate use cases and depend only on domain ports.
- **Adapters** own OpenAPI parsing, runtime validation, HTTP execution, SQLite,
  and Hermes storage. Library objects never leak upward.
- **Tools** stay thin: validate arguments, call one service, return JSON.
- **Hooks** gate promotion and optionally nudge the agent after API edits.

Read the decisions behind this design in [`docs/adr/`](docs/adr/).

---

## How Hermes uses this plugin

Hermes discovers the plugin, reads the tool schemas, and offers them to the
model like any other tool. The loop is the standard agent tool loop:

```text
1. DISCOVERY   Hermes loads plugin.yaml, imports the package, calls register(ctx).
                register() hands Hermes 8 tool schemas + 2 hooks.

2. SCHEMAS     Each schema carries a name, a description, and a JSON Schema for
                its arguments. This is the ONLY thing the model sees.

3. SELECTION   You ask in plain language. The model matches your request to a
                schema ("validate a request" -> contractguard_validate_request)
                and fills the arguments from your message and the files it can
                read.

4. EXECUTION   Hermes calls the handler. The handler validates arguments,
                runs one use case, and returns a JSON string.

5. FEEDBACK    That JSON comes back as the tool result. The model reads the
                verdict and the findings and reports them to you — or acts on
                them, which is the point.
```

### Do I need to paste code?

**No.** Natural language is enough. The tool schemas are written for it, and
each one names its safety boundary so the model picks correctly.

You say this:

```
Use ContractGuard to validate the request body {"invalid": "json"} against
operation createProduct. Do not send it.
```

And the model calls:

```json
{"tool": "contractguard_validate_request",
 "args": {"service_id": "giftshop-api", "operation_id": "createProduct",
          "body": {"invalid": "json"}, "content_type": "application/json"}}
```

The `service_id` came from the earlier registration step, the `operation_id`
from your sentence, and the body from your message. **You never write a tool
call, a JSON payload, or a parameter name by hand.**

Two things to know:

- **You still supply the facts.** Hermes cannot invent your service ID, your
  base URL, or your payload. ContractGuard reports `INCOMPLETE` with a precise
  reason when a required input is missing, rather than guessing.
- **The model chooses the tool, the tool does the verifying.** The plugin never
  asks a language model whether a schema is valid. OpenAPI-core decides that;
  the model only chooses when to ask and how to explain the answer.

### What you get back

Every tool returns the same shape, so the output is predictable:

```json
{
  "verdict": "FAIL",
  "operation_id": "getProduct",
  "method": "GET",
  "path": "/products/{product_id}",
  "request_sent": true,
  "status_code": 200,
  "content_type": "application/json",
  "duration_ms": 874,
  "violations": [
    {"code": "RESPONSE_SCHEMA_TYPE_MISMATCH", "json_pointer": "$.price",
     "message": "'49.99' is not of type 'number'",
     "expected": "number", "actual": "string"}
  ]
}
```

---

## Quickstart: one-shot setup prompt

Paste the prompt below into Hermes, Claude Code, Cursor, Codex, or any
terminal-capable coding agent. Replace `<REPO_URL>` with this repository's clone
URL. The agent sets up the environment and verifies the repository without
changing source files.

```text
Set up ContractGuard from source on this machine.

Repository: <REPO_URL>
Target directory: ./contractguard

Requirements and steps:
1. Confirm Python 3.10+ is available and record the exact version. Check for the
   Hermes CLI with `hermes --version`; record whether it is installed.
2. Clone the repository into ./contractguard and enter that directory.
3. Create an isolated environment:
   - Prefer `uv venv .venv` + `uv pip install -e ".[dev]"`.
   - Otherwise use `python3 -m venv .venv`, activate it, upgrade pip, and run
     `python -m pip install -e ".[dev]"`.
4. Run the full quality gate and stop on the first failure:
   - `pytest -q`
   - `ruff check .`
   - `ruff format --check .`
   - `mypy`
5. If Hermes is installed, make the checkout discoverable without copying it:
   `ln -s "$PWD" "${HERMES_HOME:-$HOME/.hermes}/plugins/contractguard"`
   Then run `hermes plugins doctor "$PWD" --ci` and
   `hermes plugins validate "$PWD"`, and record both results.
6. Do not modify source files. Do not install packages globally. Do not create
   credentials. Do not send requests to non-loopback hosts.
7. Report: Python version, Hermes version, every command run with pass/fail,
   the plugin path, and the single next command I should run.
```

---

## Manual setup

### 1. Clone and install

```bash
git clone https://github.com/Mohamedhazeem/ContractGuard.git contractguard
cd contractguard

uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

If you do not use `uv`:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Python 3.10 or newer is required.

### 2. Run the quality gate

```bash
pytest -q
ruff check .
ruff format --check .
mypy
```

### 3. Install as a Hermes plugin

Hermes loads native directory plugins from `$HERMES_HOME/plugins/` (default
`~/.hermes/plugins/`). The installer is the supported route — it also installs
the plugin's Python dependencies and records the source:

```bash
hermes plugins install "file://$PWD" --yes-deps --enable
hermes plugins list
```

For a quick, throwaway link during development (no dependency installation):

```bash
ln -s "$PWD" "${HERMES_HOME:-$HOME/.hermes}/plugins/contractguard"
hermes plugins enable contractguard
```

Validate exactly what Hermes loads:

```bash
hermes plugins doctor "$PWD" --ci
hermes plugins validate "$PWD"
```

`--install-deps` asks Hermes to install the plugin's declared Python
dependencies into its own environment; use the repository virtualenv for
development and the flag only when installing into a real Hermes home.

> **Restart a running gateway after installing.** Hermes installs plugin
> dependencies into a versioned environment, and a gateway that is already
> running keeps the environment it booted with. The plugin then loads but its
> libraries are missing, and tools fail with `No module named 'yaml'`. Run
> `hermes gateway restart` once after installing, and restart the Desktop app
> too if it is open.

### 4. Start a session

```bash
hermes
```

Then ask Hermes to inspect a contract, validate a payload, or verify a local
endpoint.

---

## Try it in 60 seconds

The repository ships a deterministic demo: a local API that returns HTTP 200
with a **string** where the contract declares a **number**.

```bash
pip install -e ".[demo]"
./demo/run_demo.sh
```

It starts the API on `127.0.0.1:8099` and prints five prompts to paste into
Hermes. No credentials, no internet, no production target. The full 90-second
video plan is in [`demo/STORYBOARD.md`](demo/STORYBOARD.md).

---

## Using ContractGuard

### The five-minute contract check

1. **Inspect the contract**
   > "Use ContractGuard to inspect `tests/fixtures/openapi/giftshop.yaml` and
   > list every operation, its method, path, response codes, and any coverage
   > gaps."

2. **Register the target**
   > "Register the local service `giftshop-api` at `http://127.0.0.1:8000` using
   > that OpenAPI file. Store the current spec as a candidate, not an approved
   > baseline."

3. **Preflight a request** — nothing is sent
   > "Validate this POST body against `createProduct` without sending it:
   > `{\"invalid\": \"json\"}`."

4. **Verify the live response**
   > "Test `getProduct` with `product_id=p-101` and tell me exactly which response
   > fields violate the contract."

5. **Review a contract change**
   > "Diff the candidate spec against the approved `giftshop-api` baseline and
   > classify every change. Do not promote anything."

6. **Promote only after review**
   > "Promote the candidate with SHA-256 `<exact-hash>` as version `1.1.0`."
   > Hermes asks for human approval before the new baseline becomes current.

### Tool reference

| Tool | Purpose | Sends HTTP? | Safety boundary |
|---|---|---:|---|
| `contractguard_ping` | Health check — plugin name and version | No | No arguments |
| `contractguard_inspect` | Validate a document and list operations | No | Reads one local file, size-capped, external `$ref` blocked |
| `contractguard_register` | Register a service, spec, and base URL | No | Validates slug and URL; stores candidate only |
| `contractguard_validate_request` | Offline request preflight | **No** | Always `request_sent: false`; secret headers rejected |
| `contractguard_test` | Live response verification | Yes | Loopback only, GET/HEAD only, timeouts, byte cap, no redirects |
| `contractguard_diff` | Compare candidate vs approved baseline | No | Deterministic ruleset; unsupported edits marked unclassified |
| `contractguard_history` | Read recent evidence receipts | No | Bounded, redacted, no full bodies |
| `contractguard_promote_baseline` | Approve and store a new baseline | No | Exact SHA-256, human approval, transactional compare-and-swap |

Every check tool writes a redacted evidence receipt, so `contractguard_history`
returns what actually ran, against which spec hash, with which verdict.

### Prompts that work well

```text
Inspect this OpenAPI file and tell me which operations cannot be verified because
required inputs or examples are missing.

Preflight this PATCH payload against updateProduct. Do not send it. List every
violation with its JSON Pointer.

Run the registered getProduct check again. The implementation changed; use the
same operation, target, and approved spec hash as the previous run.

Compare the candidate contract with the approved baseline. Separate breaking,
potentially breaking, non-breaking, and unclassified changes. Do not call the
result safe while unclassified changes remain.

Show me the last five evidence receipts for this service. Include verdicts,
operation IDs, spec hashes, and finding codes, but no bodies or secrets.
```

---

## Guides

### Catch a `200 OK` that violates the contract

OpenAPI declares `price` as a number. The API returns:

```json
{"id": "p-101", "name": "Keyboard", "price": "49.99"}
```

The status is `200`, but the response is not contract-compliant. ContractGuard
reports the exact failure:

```text
CONTRACTGUARD · FAIL
GET /products/{product_id} · HTTP 200
Response schema violation: $.price
Expected: number
Actual: string
Spec: sha256: 8b8...a31
Evidence: run cg_...
```

Ask Hermes to fix the serializer, then re-run the same check. The second run
uses the same operation ID, target, and spec hash, so the before/after evidence
is directly comparable.

### Reject a bad write request before it leaves the machine

A payload can be syntactically valid JSON and still violate the operation:

```json
{"invalid": "json"}
```

Preflight returns `FAIL`, lists every missing required property with its JSON
Pointer, and confirms `request_sent: false`. This is the fastest way to catch a
bad request shape without touching a development database.

### Review a breaking contract change

Compare the candidate specification with the approved baseline. ContractGuard
classifies supported changes from the perspective of existing clients:

- **Breaking:** removed path, removed operation, removed response property,
  newly required request input, incompatible type change, removed enum value.
- **Potentially breaking:** stricter constraints, response field that newly
  permits `null`, new response field under a strict schema.
- **Non-breaking:** new optional operation, new optional request field,
  description-only edit.
- **Unclassified:** complex composition or semantics the ruleset does not yet
  prove. The report says so explicitly.

A diff with unclassified changes is never presented as "no breaking changes."

### Promote only what you reviewed

Promotion requires the exact candidate hash and explicit human approval. The
transaction re-reads the file, verifies the hash, checks that the current
baseline has not changed, inserts a new row, and flips the current pointer. The
previous baseline remains in history.

### Use it as a pre-finish check

After Hermes edits API code or a spec, ask it to run the same check before
declaring the work complete. The evidence receipt gives you a defensible answer
to "did this change break the contract?" instead of a plausible summary.

---

## For hackathon judges

### Verify the project in three commands

```bash
pytest -q
hermes plugins doctor . --ci
hermes plugins validate .
```

You should see a passing test suite, a clean plugin load with matching manifest
registrations, and a successful capability probe with no core overrides.

### What to evaluate

- **Usefulness:** A real recurring problem — APIs shipping `200` responses that
  violate their published schema, and contract drift reaching clients.
- **Reliability:** Deterministic validators, stable finding codes, explicit
  verdicts, no false `PASS` on partial coverage, and a test suite that covers
  safety and adapter behaviour.
- **Polish:** Structured findings with JSON Pointers, concise evidence receipts,
  reproducible hashes, and documentation that states limitations honestly.
- **Creativity:** The agent-native loop: preflight without dispatch, live
  response proof, repair, repeat, and human-approved baseline promotion.

### Where to look

| Area | Path |
|---|---|
| Product behaviour and safety rules | `docs/plan/ContractGuard_Project_Spec.md` |
| Architecture decisions | `docs/adr/` |
| Domain vocabulary and invariants | `src/contractguard/domain/` |
| Hermes-facing handlers | `src/contractguard/tools/` and `src/contractguard/hooks/` |
| Safety and storage adapters | `src/contractguard/adapters/` |
| Test fixtures and quality gate | `tests/` |
| Agent contribution rules | `AGENTS.md` |

---

## Where it runs

ContractGuard is a **backend** plugin: it extends the agent runtime, so it works
identically wherever Hermes runs the agent — classic CLI, Ink TUI, the Desktop
app, ACP editors, and the messaging gateway. There is no separate Desktop half
and none is needed, because the plugin ships no UI.

| Surface | Tools visible to the model | Approval prompt |
|---|---:|---|
| Classic CLI | 8/8 | Prompted in the terminal |
| Ink TUI | 8/8 | Prompted in the TUI |
| **Desktop app** | **8/8** | **Prompted in the Desktop UI** |
| ACP editors | 8/8 | Prompted in the editor |
| Messaging gateway | 8/8 | Prompted in the chat platform |

Every check was measured against Hermes' own per-platform tool snapshot, not
assumed. Where no human can answer the approval prompt — cron, unattended API
runs — promotion is **declined**, not performed silently.

---

## Security model

ContractGuard reads local specification files and can send HTTP requests, so its
boundaries are explicit and enforced in code:

- **Offline by default.** Request preflight validates write-method payloads but
  never dispatches them.
- **Loopback only.** Live targets are restricted to `localhost`, `127.0.0.1`,
  and `::1`. Remote targets require a separate, reviewed SSRF/allowlist design.
- **Read methods only.** Live execution is `GET`/`HEAD`. `POST`, `PUT`, `PATCH`,
  and `DELETE` return `BLOCKED` with `request_sent: false`.
- **No redirect escape.** Redirects are reported, never followed.
- **Bounded I/O.** Five-second default budget, one-megabyte default response cap,
  streaming reads that stop at the cap, no retries, no concurrency.
- **No credential handling.** Authorization, cookie, proxy-authorization, and
  API-key headers are rejected from model-supplied arguments.
- **Redacted evidence.** Full bodies and secret headers are not persisted by
  default. Findings store pointers, type names, and safe messages.
- **Durable state isolation.** Runtime data lives in Hermes plugin storage, not
  in the repository or the installed plugin directory.
- **No core patching.** Only documented `ctx.*` APIs are used.

These constraints are intentional. A contract tool that can silently send
writes, follow redirects, or store credentials is a liability, not a guardrail.

---

## Disclosure

What this plugin does that a user should know before installing it:

- **Network calls.** The plugin makes HTTP requests, but only to a loopback
  address (`localhost`, `127.0.0.1`, `::1`) that the user registered
  explicitly, and only with `GET` or `HEAD`. It never contacts a third-party
  service, an analytics endpoint, or a telemetry backend. There is no telemetry
  and no usage reporting of any kind.
- **Reads outside the plugin's own data.** The plugin reads the OpenAPI
  document at the exact path the user (or the agent on the user's behalf) names
  in a tool call. That file is parsed, hashed, and copied into the plugin
  database. It does not scan the project directory, read `.env` files, read
  `~/.hermes/auth.json`, or read any other credential store.
- **Writes.** The plugin writes only to the Hermes-managed plugin storage
  (`plugin_data_dir` / `plugin_db`): service registrations, immutable contract
  baselines, and redacted evidence receipts. It never writes to the plugin
  installation directory and never modifies your source code.
- **Shell commands.** None. The plugin never spawns a subprocess.
- **Long-running background processes.** None. Every operation is synchronous
  and bounded; there is no worker, queue, or daemon.
- **Stored credentials.** None. Credential-bearing headers are rejected from
  tool arguments and redacted from all output. The plugin never asks for,
  stores, refreshes, or rotates a credential.
- **Human approval.** Baseline promotion is gated behind Hermes' approval
  prompt. The plugin does not auto-approve, disable guards, or spawn children
  that inherit non-interactive mode. If approval is unavailable (for example in
  an unattended run), the promotion is declined rather than performed silently.
- **Dependencies.** `openapi-core`, `openapi-spec-validator`, `httpx`, and
  `PyYAML` are installed from PyPI under the plugin's own version policy. The
  plugin does not fetch or execute code at runtime.

Full detail in [`SECURITY.md`](SECURITY.md).

---

## Configuration

Settings are immutable, validated on construction, and resolved from
`CONTRACTGUARD_*` environment variables.

| Variable | Default | Bounds | Purpose |
|---|---:|---:|---|
| `CONTRACTGUARD_MAX_SPEC_BYTES` | 2 MiB | 1 KiB – 16 MiB | Maximum OpenAPI document size |
| `CONTRACTGUARD_MAX_REQUEST_BODY_BYTES` | 256 KiB | 1 KiB – 4 MiB | Preflight body serialization cap |
| `CONTRACTGUARD_MAX_RESPONSE_BYTES` | 1 MiB | 1 KiB – 8 MiB | Live response read cap |
| `CONTRACTGUARD_HTTP_TIMEOUT_SECONDS` | 5.0 | 0.1 – 30.0 | Total per-request budget |
| `CONTRACTGUARD_MAX_OPERATIONS_PER_RUN` | 1 | 1 – 5 | Live operations per call |
| `CONTRACTGUARD_MAX_HISTORY_RECORDS` | 10 | 1 – 20 | History page size |

Malformed or out-of-bounds values fail closed. Safety-critical behaviour — live
methods, target scope, redirects, TLS verification, proxy inheritance, retries,
and concurrency — is not environment-tunable.

---

## Project structure

```text
contractguard/
├── plugin.yaml                  # Hermes manifest
├── __init__.py                  # Hermes bootstrap: register(ctx)
├── pyproject.toml               # Packaging, dependencies, quality tooling
├── LICENSE                      # MIT
├── SECURITY.md                  # Threat model and disclosure
├── CHANGELOG.md                 # Release notes
├── AGENTS.md                    # Rules for AI coding agents
├── .github/workflows/ci.yml     # Quality gate + Hermes plugin validation
├── docs/
│   ├── adr/                     # Architecture Decision Records
│   └── plan/                    # Product specification
├── src/contractguard/
│   ├── config.py                # Immutable settings and safety constants
│   ├── domain/                  # Pure models, ports, errors
│   ├── services/                # Use-case orchestration
│   ├── adapters/                # SQLite, HTTP, OpenAPI, Hermes storage
│   ├── tools/                   # Tool schemas and handlers
│   └── hooks/                   # Approval and verification hooks
├── tests/
│   ├── conftest.py              # Spec and in-memory SQLite fixtures
│   ├── unit/
│   ├── integration/
│   └── fixtures/openapi/
├── spikes/                      # One-shot technical spikes (not shipped)
└── demo/                        # Local walkthrough fixture
```

---

## Development

```bash
pytest -q                                   # full suite
pytest tests/unit -q                        # fast, pure tests
pytest -m integration -q                    # adapter and local-API tests
pytest --cov=contractguard --cov-report=term-missing
ruff check .
ruff format --check .
mypy
```

Rules:

- Unit tests do not touch the network or sleep.
- Integration tests use in-memory SQLite and loopback fixtures.
- Every fixed defect gets a regression test with the exact finding code and JSON
  Pointer.
- Security tests cover blocked methods, non-loopback targets, redirects,
  oversized responses, secret headers, and missing input.
- A change is not complete until `pytest`, `ruff`, and `mypy` pass.

See [`AGENTS.md`](AGENTS.md) for the full contribution contract.

---

## FAQ

**Does preflight ever send the request?**
No. It reports `request_sent: false` by construction.

**Can ContractGuard send POST, PUT, PATCH, or DELETE?**
Not for live verification. Those methods are preflight-only. This is a safety
decision, not a missing flag.

**Can I point it at production?**
Not in this release. Live targets are loopback-only until remote-origin
allowlisting and DNS/IP validation are designed and tested.

**Does HTTP 200 mean the check passed?**
No. The response body, status declaration, and media type are validated
independently of the status code.

**Where is data stored?**
In the Hermes-managed plugin database and data directory, never in the plugin
installation directory. Baselines are stored as normalized JSON plus SHA-256.

**Does it modify Hermes core?**
No. It uses documented plugin APIs and is rejected by the catalog validator if
it tries to override core behaviour.

**Which OpenAPI versions are supported?**
OpenAPI 3.0.x, 3.1.x, and 3.2.x. External `$ref` resolution is blocked.

**What happens when an operation cannot be tested?**
It returns `INCOMPLETE` with the missing input or unsupported construct. It never
returns `PASS` for work that did not run.

---

## Contributing

Read [`AGENTS.md`](AGENTS.md) before opening a change. Preserve the layer
boundaries, keep the domain pure, never patch Hermes core, never commit with
failing tests, and never let an untested or skipped check report `PASS`.

Issues and pull requests should include the exact verdict, finding code, and JSON
Pointer affected by the change.

## License

ContractGuard is released under the [MIT License](LICENSE).

Copyright © 2026 ContractGuard contributors.
