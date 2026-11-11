# Demo storyboard — 90 seconds

A single reproducible walkthrough that shows the whole value proposition:
**a request blocked before dispatch, a live API that violates its own contract,
and the same check passing after the fix.**

Every prompt below is plain natural language. No code, no JSON payloads pasted
into the chat, no tool names memorised by the viewer.

## Setup (before recording)

```bash
cd /path/to/contractguard
pip install -e ".[demo]"          # or: uv pip install -e ".[demo]"
hermes plugins install "file://$PWD" --yes-deps --enable
hermes gateway restart             # required: a running gateway keeps its old
                                   # dependency environment and cannot import
                                   # the plugin's libraries until it restarts
./demo/run_demo.sh                 # starts the broken-mode API on :8099
hermes                              # start the chat (or use the Desktop app)
```

> **Why the restart matters.** Hermes installs plugin dependencies into a
> versioned environment. A gateway that was already running keeps the
> environment it booted with, so the plugin loads but its libraries are missing.
> `hermes gateway restart` is the documented remedy. This is the single most
> common first-run stumble, so show it in the README rather than hiding it.

## Shot list

| Time | Shot | What the viewer sees | Why it matters |
|---:|---|---|---|
| 0:00–0:08 | Terminal + `demo/run_demo.sh` | `{"id":"p-101","name":"Keyboard","price":"49.99"}` — HTTP 200, price is a **string** | The bug is visible before the tool exists. Status is 200; the payload is wrong. |
| 0:08–0:18 | Prompt 1: inspect | `status: VALID`, 3 operations, SHA-256 shown | Hermes reads the contract and reports its identity. |
| 0:18–0:28 | Prompt 2: register | service registered, candidate baseline stored, hash shown | The target and contract are pinned before anything runs. |
| 0:28–0:42 | Prompt 3: preflight | `FAIL`, `request_sent: false`, 8 findings, each with a JSON Pointer (`$.id`, `$.name`, …) | **The bad request never leaves the machine.** This is the "gatekeeper" moment. |
| 0:42–0:55 | Prompt 4: live test | `FAIL`, `status_code: 200`, `$.price expected number, actual string` | The headline: HTTP 200 is **not** proof of correctness. |
| 0:55–1:05 | Show the fix | `DEMO_BROKEN=0` (or edit one line of the serializer) | The defect is ordinary and tiny — exactly the class of bug that ships. |
| 1:05–1:18 | Prompt 5: re-run | `PASS`, same operation, same spec hash, 0 violations | Determinism: same check, same inputs, different outcome. Evidence, not opinion. |
| 1:18–1:28 | Prompt: history | receipts for preflight / test / diff with verdicts, hashes, durations | Every run leaves an auditable trail. |
| 1:28–1:30 | Closing card | "ContractGuard — evidence before you ship." | |

## Prompts (paste verbatim)

**1 — Inspect**

```
Use ContractGuard to inspect demo/openapi.yaml and list every operation.
```

**2 — Register**

```
Use ContractGuard to register a service "giftshop-api" from demo/openapi.yaml
with base URL http://127.0.0.1:8099.
```

**3 — Preflight (never sends)**

```
Use ContractGuard to validate the request body {"invalid": "json"} against
operation createProduct. Do not send it. List every violation with its JSON
Pointer.
```

**4 — Live check (the proof)**

```
Use ContractGuard to run the getProduct check with product_id=p-101 and tell me
exactly which response fields violate the contract.
```

**5 — Re-run after the fix**

```
Use ContractGuard to run the getProduct check again, same operation and same
spec hash.
```

**6 — Evidence**

```
Use ContractGuard to show me the recent evidence receipts for giftshop-api.
```

## Recording notes

- Use a **large terminal font** (14pt+). The JSON pointers are the payoff; they
  must be legible.
- Pre-warm the chat so the first prompt is not spent on model warm-up. Run
  prompt 1 once before recording and then start the capture.
- Keep the API's JSON visible in a second pane or split terminal for shot 1 so
  the viewer sees the wrong type before the tool says so.
- The demo needs **no credentials, no internet, and no production target** — it
  is a local loopback API. Say this out loud; judges ask.
- If the model is slow, cut shot 6 (history). Never cut shot 4 (the live proof)
  or shot 3 (the blocked request) — those two carry the whole argument.

## Backup plan

If the live demo misbehaves on stage, the story still holds with these two
one-liners, which need no model at all:

```bash
curl -s http://127.0.0.1:8099/products/p-101     # shows price as a string
pytest tests/unit -q                              # shows the safety suite
```
