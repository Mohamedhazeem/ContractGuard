# Catalog submission checklist

Everything needed to list ContractGuard in the Hermes plugin catalog.

## Status

| Item | State |
|---|---|
| Public repository | Done — https://github.com/Mohamedhazeem/contractguard (public, `main`) |
| Loadable plugin at the pinned commit | Done — `plugin.yaml` + `__init__.py` with `register(ctx)` |
| Local validation (`hermes plugins validate --install-deps`) | Done — passes |
| Plugin doctor (`hermes plugins doctor . --ci`) | Done — 8 tools, 2 hooks |
| Quality gate (pytest / ruff / mypy) | Done — 41 passed, 0 issues |
| `requires_hermes` in `plugin.yaml` | Done — `>=0.21.6` |
| `requires_hermes` in the catalog entry | Done — `>=0.21.6` (same floor) |
| Version consistency (`plugin.yaml` / `pyproject.toml` / entry) | Done — `0.2.0` |
| Manifest `provides_tools` / `provides_hooks` match registration | Done — validated |
| Entry `capabilities` match the manifest | Done — 8 tools, 2 hooks |
| Dependency floors verified against Hermes core pins | Done — see below |
| Dependency upper bounds | Done — every dependency has an upper bound |
| Release-age quarantine in CI | Done — `--exclude-newer "3 days"` |
| Risky behaviour disclosed in the README | Done — "Disclosure" section |
| Risky behaviour disclosed in the PR description | Done — `submission/PR_DESCRIPTION.md` |
| `SECURITY.md` | Done |
| No self-updating code | Done — no update fetcher, no remote loader |
| No core overrides | Done — validator's "no core override" check passes |
| No private core imports | Done — `plugins.plugin_storage` is in the published plugin API |
| No compiled binaries / bytecode / archives | Done — source only |
| No credential reads outside Hermes routes | Done — no `.env`, no `auth.json` |
| Approvals respected, fails closed unattended | Done — promotion is approval-gated |
| Entry file structurally valid | Done — validated with Hermes' own script |
| Catalog entry file prepared | `submission/plugin-catalog-entry.yaml` (set the real `sha`) |
| PR description prepared | `submission/PR_DESCRIPTION.md` |
| Entry PR opened against `NousResearch/hermes-agent` | **Not done — needs a human** |
| 90-second demo video posted on X | **Not done — needs a human** |
| Official submission form | **Not done — needs a human** |

## Steps to submit

1. Push the current state and record the full 40-character SHA:

   ```bash
   git rev-parse HEAD
   ```

2. Put that SHA in `submission/plugin-catalog-entry.yaml` (replace the
   placeholder `0000...`).

3. Validate the entry against Hermes' own structural validator:

   ```bash
   python3 scripts/validate_plugin_catalog.py plugin-catalog/contractguard.yaml
   ```

   (Requires `ruamel.yaml==0.18.17`.)

4. Validate the plugin itself at that exact commit — this is what catalog CI
   runs:

   ```bash
   git clone --no-checkout https://github.com/Mohamedhazeem/contractguard
   cd contractguard && git checkout <SHA>
   hermes plugins validate . --install-deps
   ```

5. Open a PR against `NousResearch/hermes-agent` adding
   `plugin-catalog/contractguard.yaml`, using the description in
   `submission/PR_DESCRIPTION.md`.

6. Wait for the **Plugin Catalog CI** job to go green, then respond to the
   maintainer's review.

7. Post the demo video on X tagging `@NousResearch` and submit the official
   form with both links.

## Dependency floor evidence

Hermes pins `jsonschema==4.26.0`, `httpx==0.28.1`, and `PyYAML==6.0.3`. The
floors below were resolved and the test suite run against each combination.

| Dependency | Declared range | Why that floor |
|---|---|---|
| `openapi-core` | `>=0.23,<0.24` | 0.21 and 0.22 reject OpenAPI 3.2 documents ("spec not detected"). 0.23 is the first release with 3.2 support. |
| `openapi-spec-validator` | `>=0.8.5,<0.9` | `openapi-core>=0.23` imports `OpenAPIV32SpecValidator`, which exists only from 0.8.2 — but 0.8.2–0.8.4 require `jsonschema<4.25`, which conflicts with Hermes' `jsonschema==4.26.0` pin. 0.8.5 is the first version satisfying both. |
| `httpx` | `>=0.27,<0.29` | Hermes pins `httpx==0.28.1`, inside the range. Verified against 0.27.2 and 0.28.1. |
| `PyYAML` | `>=6.0.1,<7` | Hermes pins `PyYAML==6.0.3`, inside the range. |

Verified combination (Hermes' exact pins + our floors): `openapi-core==0.23.0`,
`openapi-spec-validator==0.8.5`, `jsonschema==4.26.0`, `referencing==0.37.0`,
`httpx==0.28.1`, `PyYAML==6.0.3` — 41 tests pass.

## Known limitations (also in the entry's `known_issues`)

- Live verification targets loopback addresses only.
- Live requests are limited to `GET` and `HEAD`.
- The compatibility ruleset is bounded; complex schema composition is reported
  as `unclassified` rather than guessed.
