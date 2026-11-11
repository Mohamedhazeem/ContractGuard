# PR description — ContractGuard plugin catalog entry

Ready-to-paste content for the PR that adds `plugin-catalog/contractguard.yaml`
to `NousResearch/hermes-agent`.

> Before opening: confirm the `sha` in the entry file is the full
> 40-character commit you validated. Bump `version` in the same PR when the pin
> changes.

---

## What this plugin does

ContractGuard is a native Hermes plugin for **API contract assurance**. It gives
Hermes deterministic tools to prove that an HTTP API still matches its OpenAPI
contract:

- `contractguard_inspect` — validate an OpenAPI document and list its
  operations, declared response codes, required inputs, and coverage gaps.
- `contractguard_register` — register a service with an explicit loopback base
  URL. Stores the current spec as a *candidate*, never as an approved baseline.
- `contractguard_validate_request` — validate a proposed request (path, query,
  headers, JSON body) against the operation **without sending it**. Always
  reports `request_sent: false`.
- `contractguard_test` — execute a bounded live `GET`/`HEAD` request against the
  registered loopback target and validate the **actual** response. An HTTP 200
  with a wrong field type is a `FAIL`, not a pass.
- `contractguard_diff` — compare a candidate contract with the human-approved
  baseline and classify changes as breaking, potentially breaking, non-breaking,
  or unclassified.
- `contractguard_history` — read bounded, redacted evidence receipts.
- `contractguard_promote_baseline` — promote an exact candidate SHA-256 to the
  approved baseline, behind Hermes' human-approval gate.
- `contractguard_ping` — health check.

**The problem it solves.** An API can return `200 OK` while violating its own
published schema — a numeric `price` serialized as `"49.99"`, a required
response property that disappeared after a refactor, a request parameter that
changed type. A smoke test that only checks for `200` cannot see any of it.
Existing validators (Wiretap, Schemathesis) live outside the agent's coding
loop, so the evidence is disconnected from the code change and drift is reviewed
late or not at all.

ContractGuard puts deterministic verification inside the loop: preflight →
live verification → structured findings with JSON Pointers → the agent repairs
the code → the same check runs again against the same spec hash. It also keeps a
human-approved contract baseline so a candidate spec is diffed against what was
actually approved, and promotion is gated behind an approval prompt.

## Hermes surfaces used

| Surface | Usage |
|---|---|
| `ctx.register_tool` | 8 tools (listed in the entry's `capabilities`) |
| `ctx.register_hook` | 2 hooks: `pre_tool_call` (approval gate) and `pre_verify` (one-shot nudge) |
| `plugins.plugin_storage` | `plugin_data_dir` / `plugin_db` for durable storage |

No other Hermes surface is used: no middleware, no provider plugins, no Desktop
surface, no skills, no slash commands, no locale packs.

- `pre_tool_call` gates **only** `contractguard_promote_baseline`. No other
  tool is gated.
- `pre_verify` is a one-shot nudge (fires on `attempt == 0` only) asking Hermes
  to run `contractguard_diff` and/or `contractguard_test` after API or contract
  files change. It performs no I/O and never runs a check inside the hook.

## Surface compatibility (CLI and Desktop)

ContractGuard is a **backend** plugin: it extends the agent runtime, so it works
identically wherever Hermes runs the agent — classic CLI, Ink TUI, Desktop app,
ACP editors, and the messaging gateway. There is no separate Desktop half and
none is needed, because the plugin ships no UI.

Verified against Hermes `0.23.1` with the plugin installed through the real
installer (`hermes plugins install ... --ref <sha> --enable`):

| Surface | Tools visible to the model | `pre_tool_call` | `pre_verify` |
|---|---:|---|---|
| CLI (`cli`) | 8/8 | registered | registered |
| Ink TUI (`tui`) | 8/8 | registered | registered |
| **Desktop (`desktop`)** | **8/8** | **registered** | **registered** |
| ACP (`acp`) | 8/8 | registered | registered |
| Telegram (`telegram`) | 8/8 | registered | registered |

The measurement is the agent's own tool snapshot
(`model_tools.get_tool_definitions(enabled_toolsets=...)`) per platform, not an
inference: every surface resolves the `contractguard` toolset and exposes all 8
tools.

**Approval on Desktop.** The `pre_tool_call` hook returns
`{"action": "approve", "message": ...}`, which Hermes routes to its human
approval gate (`tools.approval.request_tool_approval`) — the same gate used for
dangerous shell patterns, so the model cannot skip it. On Desktop the prompt is
rendered by the local viewer (`gui` is one of Hermes' local interactive
sources, alongside `cli`, `tui`, `acp`), so the operator answers it in the
Desktop UI exactly as in the CLI. Where no human can answer — cron, unattended
API runs — the gate **fails closed** and the promotion is declined rather than
performed silently.

## Disclosure (catalog rule 13)

- **Network calls:** HTTP requests are made **only** to a loopback address
  (`localhost`, `127.0.0.1`, `::1`) that the user registered explicitly, and
  **only** with `GET` or `HEAD`. Write methods are validated offline and are
  never dispatched. No third-party services are contacted. No telemetry, no
  analytics, no usage reporting.
- **Reads outside the plugin's own data:** the plugin reads the OpenAPI
  document at the exact path named in a tool call. It does not scan the project
  directory, read `.env` files, read `~/.hermes/auth.json`, or read any other
  credential store.
- **Writes:** only the Hermes-managed plugin database — service registrations,
  immutable contract baselines (normalized JSON plus SHA-256), and redacted
  evidence receipts. Never the plugin installation directory; never the user's
  source code.
- **Shell commands:** none. The plugin never spawns a subprocess.
- **Long-running background processes:** none. Every operation is synchronous
  and bounded; there is no worker, queue, or daemon.
- **Stored credentials:** none. `Authorization`, `Cookie`, `Proxy-Authorization`,
  and API-key headers are rejected from model-supplied tool arguments and
  redacted from all output. The plugin never asks for, stores, refreshes, or
  rotates a credential.
- **Approvals:** baseline promotion is gated behind Hermes' approval prompt.
  The plugin does not auto-approve, disable guards, or spawn children that
  inherit non-interactive mode.
- **Dependencies:** `openapi-core`, `openapi-spec-validator`, `httpx`, and
  `PyYAML` install from PyPI under the plugin's own bounded version policy. The
  plugin fetches and executes no code at runtime.

The same disclosure appears in the plugin's README and in `SECURITY.md`.

## Compatibility metadata (catalog rule 14)

- `requires_hermes: ">=0.21.6"` — the first Hermes release that ships the
  `pre_verify` hook, the `plugins.plugin_storage` helpers, and manifest-level
  `requires_hermes` support. The same floor is declared in `plugin.yaml`, so
  older Hermes releases skip the plugin rather than failing to load it.
- `version: "0.2.0"` matches the pinned commit and the version in
  `plugin.yaml`.

## Verification performed at the pinned commit

```
hermes plugins validate . --install-deps   # validation passed
hermes plugins doctor . --ci               # 8 tools, 2 hooks
pytest -q                                   # 41 passed
ruff check . / ruff format --check .       # passed
mypy                                        # 0 issues
```

The pinned commit was also installed through the real installer into an isolated
Hermes home (`hermes plugins install Mohamedhazeem/contractguard --ref <sha>
--yes-deps --enable`) and exercised end to end through Hermes' own tool
registry:

```text
register -> giftshop-api 98dc9766140d candidate: True
test     -> FAIL status 200 sent True
             RESPONSE_SCHEMA_TYPE_MISMATCH $.price number -> string
history  -> 1 receipt(s): [('test', 'FAIL')]
```

The repository's CI workflow runs the same quality gate plus both Hermes
validation commands on every push, with a 3-day dependency release-age
quarantine.

## Dependency floors

Hermes pins `jsonschema==4.26.0`, `httpx==0.28.1`, and `PyYAML==6.0.3`. Every
declared dependency has an upper bound, and the floors are the oldest versions
that work under those pins:

| Dependency | Range | Why that floor |
|---|---|---|
| `openapi-core` | `>=0.23,<0.24` | 0.21 and 0.22 reject OpenAPI 3.2 documents ("spec not detected"); 0.23 is the first with 3.2 support. |
| `openapi-spec-validator` | `>=0.8.5,<0.9` | `openapi-core>=0.23` imports `OpenAPIV32SpecValidator` (0.8.2+), but 0.8.2–0.8.4 pin `jsonschema<4.25`, conflicting with Hermes' `jsonschema==4.26.0`. 0.8.5 is the first version satisfying both. |
| `httpx` | `>=0.27,<0.29` | Hermes pins `httpx==0.28.1`, inside the range. |
| `PyYAML` | `>=6.0.1,<7` | Hermes pins `PyYAML==6.0.3`, inside the range. |

## Screenshots

None. ContractGuard has no UI: its output is the Hermes tool result. The
recorded 90-second demo walkthrough is linked from the repository README.

## Notes for the reviewer

- The plugin ships no compiled binaries, no bytecode, and no archives — only
  reviewable source.
- It patches nothing in Hermes core and imports only the documented public
  plugin API. `plugins.plugin_storage` is in Hermes' published plugin API list;
  the validator's private-import lint reports no findings.
- The plugin is backend-only, so there is no Desktop half to review and no
  Desktop SDK surface is used.
- Baselines are immutable and content-addressed: editing the OpenAPI file on
  disk cannot change what was approved. Promotion re-reads and re-hashes the
  candidate and uses a transactional compare-and-swap.
- The compatibility diff is a small, explicit, versioned ruleset. Complex schema
  composition is reported as `unclassified` rather than guessed, and the report
  says so.
- Evidence receipts store verdicts, spec hashes, JSON Pointers, and type names —
  never full request or response bodies.
