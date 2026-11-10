# ContractGuard demo fixture

Deterministic FastAPI app used for the recorded workflow. The only deliberate
defect is the type of `price` in the GET response: a string in broken mode and
a number in fixed mode. The HTTP status is 200 in both modes.

## Files

```text
demo/
├── README.md
├── app.py          # FastAPI app with broken/fixed price serialization
└── openapi.yaml    # contract used by inspect, preflight, test, and diff
```

## Run

Broken mode (default):

```bash
pip install -e ".[demo]"
DEMO_BROKEN=1 uvicorn demo.app:app --host 127.0.0.1 --port 8000
```

Fixed mode:

```bash
DEMO_BROKEN=0 uvicorn demo.app:app --host 127.0.0.1 --port 8000
```

## Demo narrative

1. `contractguard_inspect` validates `demo/openapi.yaml`.
2. `contractguard_validate_request` rejects `{"invalid": "json"}` and reports
   `request_sent: false`.
3. `contractguard_test` calls the broken `GET /products/p-101`; HTTP 200 but a
   response schema violation at `$.price` produces `FAIL`.
4. Hermes edits the demo serializer (or sets `DEMO_BROKEN=0`).
5. The same check returns `PASS`.
6. `contractguard_diff` compares a candidate contract with the approved baseline
   and classifies the removed response property as breaking.

Safety: the demo target is loopback only, uses GET, disables redirects, and does
not require credentials.
PY