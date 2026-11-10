# ContractGuard demo fixture

This directory will contain the deterministic FastAPI app used for the recorded
workflow. It is scheduled for **Slice 8** in
[`docs/plan/ContractGuard_Implementation.md`](../docs/plan/ContractGuard_Implementation.md);
the scaffold intentionally does not ship untested demo code.

## Planned shape

| Endpoint | Behaviour |
|---|---|
| `GET /products/{product_id}` | Returns `{"id": "p-101", "name": "Keyboard", "price": 49.99}` |
| `GET /products/{product_id}` in broken mode | Returns the same body with `"price": "49.99"` and HTTP 200 |
| `POST /products` | Declared in the contract; preflight-only in the MVP, never dispatched |

The deliberate failure is a **type** violation, not a status-code failure. The
demo exists to prove that HTTP 200 does not mean the response obeys its contract.

## Planned files

```text
demo/
├── README.md       # this file
├── app.py          # FastAPI app with broken/fixed price serialization
├── openapi.yaml    # contract used by inspect, preflight, test, and diff
└── state.json      # deterministic toggle between broken and fixed modes
```

## Planned commands

```bash
pip install -e ".[demo]"
uvicorn demo.app:app --host 127.0.0.1 --port 8000
```

## Demo narrative

1. `contractguard_inspect` validates the demo contract.
2. `contractguard_validate_request` rejects `{"invalid": "json"}` and reports
   `request_sent: false`.
3. `contractguard_test` calls the broken `GET /products/p-101`; HTTP 200 but a
   response schema violation at `$.price` produces `FAIL`.
4. Hermes edits the demo serializer.
5. The same check returns `PASS`.
6. `contractguard_diff` compares a candidate contract with the approved baseline
   and classifies the removed response property as breaking.

Safety: the demo target is loopback only, uses GET, disables redirects, and does
not require credentials.
