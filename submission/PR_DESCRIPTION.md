# PR description — ContractGuard plugin catalog entry

Copy this into the PR that adds `plugin-catalog/contractguard.yaml` to
`NousResearch/hermes-agent`.

> Before opening: replace the placeholder `sha` in the entry file with the
> full 40-character commit of this repository that you validated. Bump
> `version` in the same PR when the pin changes.

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

The problem it solves: an API can return `200 OK` while violating its own
published schema (a numeric `price` serialized as `"49.99"`), and contracts
drift from implementations for weeks. Existing validators live outside the
agent's coding loop, so the evidence is disconnected from the code change.
ContractGuard puts deterministic verification inside the loop: preflight →
live verification → structured findings → the agent repairs the code → the same
check runs again.

## Hermes surfaces used

- `ctx.register_tool` — 8 tools.
- `ctx.register_hook` — 2 hooks:
  - `pre_tool_call` gates **only** `contractguard_promote_baseline` behind
    Hermes' human-approval gate. No other tool is gated.
  - `pre_verify` is a one-shot nudge asking Hermes to run `contractguard_diff`
    and/or `contractguard_test` after API or contract files change. It performs
    no I/O and never runs inside the hook callback.
- `plugins.plugin_storage` (`plugin_data_dir`, `plugin_db`) — durable storage
  for service registrations, immutable contract baselines, and evidence
  receipts.

No other Hermes surface is used. The plugin does not register middleware,
providers, Desktop surfaces, skills, slash commands, or locale packs.

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
  inherit non-interactive mode. When approval is unavailable (for example in an
  unattended run), the promotion is declined rather than performed silently.
- **Dependencies:** `openapi-core`, `openapi-spec-validator`, `httpx`, and
  `PyYAML` install from PyPI under the plugin's own bounded version policy. The
  plugin fetches and executes no code at runtime.

The same disclosure appears in the plugin's README and in `SECURITY.md`.

## Compatibility metadata (catalog rule 14)

- `requires_hermes: ">=0.21.6"` — the first Hermes release that ships the
  `pre_verify` hook, the `plugins.plugin_storage` helpers, and manifest-level
  `requires_hermes` support. The same floor is declared in `plugin.yaml`, so
  older Hermes releases skip the plugin instead of failing to load it.
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

The repository's CI workflow runs the same quality gate plus both Hermes
validation commands on every push, with a 3-day dependency release-age
quarantine.

## Screenshots

None. ContractGuard has no UI: its output is the Hermes tool result. The
recorded 90-second demo walkthrough is linked from the repository README.

## Notes for the reviewer

- The plugin ships no compiled binaries, no bytecode, and no archives — only
  reviewable source.
- It patches nothing in Hermes core and imports only the documented public
  plugin API (`plugins.plugin_storage` is in the published plugin API list).
- Baselines are immutable and content-addressed: editing the OpenAPI file on
  disk cannot change what was approved. Promotion re-reads and re-hashes the
  candidate and uses a transactional compare-and-swap.
- The compatibility diff is a small, explicit, versioned ruleset. Complex schema
  composition is reported as `unclassified` rather than guessed, and the report
  says so.
