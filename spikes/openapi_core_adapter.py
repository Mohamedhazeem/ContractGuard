"""Slice 0 adapter spike for ContractGuard.

This script proves the highest-risk technical assumption in the project: that a
custom request/response adapter can satisfy the protocols required by
``openapi-core`` and that validation produces field-level findings.

Run with the project's virtual environment:

    PYTHONPATH=src .venv/bin/python spikes/openapi_core_adapter.py

Exit code 0 means the spike passed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from openapi_core.datatypes import RequestParameters

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from contractguard.adapters.openapi import (  # noqa: E402
    OpenApiRequestAdapter,
    OpenApiResponseAdapter,
    make_openapi,
    validate_request,
    validate_response,
)

SPEC = {
    "openapi": "3.0.3",
    "info": {"title": "ContractGuard adapter spike", "version": "1.0.0"},
    "paths": {
        "/products": {
            "post": {
                "operationId": "createProduct",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["id", "name", "price"],
                                "properties": {
                                    "id": {"type": "string"},
                                    "name": {"type": "string"},
                                    "price": {"type": "number"},
                                },
                            }
                        }
                    },
                },
                "responses": {"201": {"description": "created"}},
            }
        },
        "/products/{product_id}": {
            "get": {
                "operationId": "getProduct",
                "parameters": [
                    {
                        "name": "product_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {
                    "200": {
                        "description": "product",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["id", "name", "price"],
                                    "properties": {
                                        "id": {"type": "string"},
                                        "name": {"type": "string"},
                                        "price": {"type": "number"},
                                    },
                                }
                            }
                        },
                    }
                },
            }
        },
    },
}


def main() -> int:
    openapi = make_openapi(SPEC)

    # --- Request preflight: invalid body must produce all three missing-field
    # findings, and the request must never be sent.
    request = OpenApiRequestAdapter(
        method="POST",
        host_url="http://127.0.0.1:8000",
        path="/products",
        full_url_pattern="http://127.0.0.1:8000/products",
        parameters=RequestParameters(),
        body=json.dumps({"invalid": "json"}).encode("utf-8"),
        content_type="application/json",
    )
    request_errors = validate_request(openapi, request)
    print("REQUEST PREFLIGHT")
    print(f"  errors: {len(request_errors)}")
    for error in request_errors:
        print(f"  - {type(error).__name__}: {getattr(error, '__cause__', error)}")

    # --- Live response: HTTP 200 with price as a string is a contract failure.
    response_request = OpenApiRequestAdapter(
        method="GET",
        host_url="http://127.0.0.1:8000",
        path="/products/p-101",
        full_url_pattern="http://127.0.0.1:8000/products/{product_id}",
        parameters=RequestParameters(path={"product_id": "p-101"}),
        body=None,
        content_type="",
    )
    response = OpenApiResponseAdapter(
        status_code=200,
        headers={},
        content_type="application/json",
        data=json.dumps({"id": "p-101", "name": "Keyboard", "price": "49.99"}).encode("utf-8"),
    )
    response_errors = validate_response(openapi, response_request, response)
    print("LIVE RESPONSE")
    print(f"  errors: {len(response_errors)}")
    for error in response_errors:
        print(f"  - {type(error).__name__}: {getattr(error, '__cause__', error)}")

    if len(request_errors) != 1:
        print("FAIL: expected exactly one request-level error")
        return 1
    cause = getattr(request_errors[0], "__cause__", None)
    schema_errors = getattr(cause, "schema_errors", ()) if cause is not None else ()
    if len(schema_errors) != 3:
        print(f"FAIL: expected 3 missing-property findings, got {len(schema_errors)}")
        return 1

    if len(response_errors) != 1:
        print("FAIL: expected exactly one response-level error")
        return 1
    response_cause = getattr(response_errors[0], "__cause__", None)
    response_schema_errors = (
        getattr(response_cause, "schema_errors", ()) if response_cause is not None else ()
    )
    if not any("not of type 'number'" in str(err) for err in response_schema_errors):
        print("FAIL: expected a price type mismatch")
        return 1

    print("SPIKE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
