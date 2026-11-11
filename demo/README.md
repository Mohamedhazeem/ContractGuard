# ContractGuard demo fixture

A deterministic FastAPI app and a 90-second walkthrough that shows the whole
value proposition: **a request blocked before dispatch, a live API that
violates its own contract, and the same check passing after the fix.**

## Files

```text
demo/
├── README.md         # this file
├── STORYBOARD.md     # the 90-second video plan, with exact prompts
├── run_demo.sh       # one command: starts the API and prints the prompts
├── app.py            # FastAPI app with broken/fixed price serialization
└── openapi.yaml      # the contract used by inspect, preflight, test, and diff
```

## Run it

```bash
pip install -e ".[demo]"

./demo/run_demo.sh                # broken mode: price is "49.99" (a string)
DEMO_BROKEN=0 ./demo/run_demo.sh  # fixed mode:  price is 49.99  (a number)
```

The launcher starts the API on `127.0.0.1:8099`, prints the current response,
and prints five prompts to paste into Hermes. Stop it with Ctrl+C.

Safety: the demo target is loopback only, uses GET, disables redirects, and
needs no credentials.

## The five prompts

1. **Inspect** — `Use ContractGuard to inspect demo/openapi.yaml and list every
   operation.`
2. **Register** — `Use ContractGuard to register a service "giftshop-api" from
   demo/openapi.yaml with base URL http://127.0.0.1:8099.`
3. **Preflight** — `Use ContractGuard to validate the request body
   {"invalid": "json"} against operation createProduct. Do not send it.`
4. **Live check** — `Use ContractGuard to run the getProduct check with
   product_id=p-101 and tell me exactly which response fields violate the
   contract.`
5. **Re-run** — `Use ContractGuard to run the getProduct check again, same
   operation and same spec hash.`

Expected results:

| Prompt | Result |
|---|---|
| 1 | `status: VALID`, 3 operations, SHA-256 of the contract |
| 2 | service registered, candidate baseline stored |
| 3 | `FAIL`, `request_sent: false`, every violation with a JSON Pointer |
| 4 | `FAIL`, `status_code: 200`, `$.price expected number, actual string` |
| 5 | `PASS` (after restarting the API with `DEMO_BROKEN=0`) |

## Before recording

If ContractGuard was just installed, restart a running gateway so it picks up
the plugin's Python dependencies:

```bash
hermes gateway restart
```

A gateway that is already running keeps the dependency environment it booted
with; the plugin then loads but its libraries are missing. This is the one
setup step worth showing on camera — it is exactly the kind of real-world
friction a judge will hit.

## The story in one line

OpenAPI says `price` is a number. The API returns `"49.99"` with HTTP 200.
Every ordinary test passes. ContractGuard does not.
