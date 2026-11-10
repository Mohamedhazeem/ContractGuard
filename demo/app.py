"""Deterministic FastAPI fixture used by the ContractGuard demo.

Run in broken mode (default):

    DEMO_BROKEN=1 uvicorn demo.app:app --host 127.0.0.1 --port 8000

Run in fixed mode:

    DEMO_BROKEN=0 uvicorn demo.app:app --host 127.0.0.1 --port 8000

The only deliberate defect is the type of ``price`` in the GET response: a
string in broken mode and a number in fixed mode. The HTTP status is 200 in
both modes so the demo proves that HTTP 200 is not proof of contract compliance.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI(title="ContractGuard Demo", version="1.0.0")

PRODUCT = {
    "id": "p-101",
    "name": "Keyboard",
}

BROKEN = os.environ.get("DEMO_BROKEN", "1").lower() not in {"0", "false", "no", "off"}


def _price() -> Any:
    return "49.99" if BROKEN else 49.99


@app.get("/products/{product_id}")
def get_product(product_id: str) -> JSONResponse:
    if product_id != PRODUCT["id"]:
        raise HTTPException(status_code=404, detail="Product not found")
    return JSONResponse({"id": PRODUCT["id"], "name": PRODUCT["name"], "price": _price()})


@app.post("/products", status_code=201)
def create_product(payload: dict[str, Any]) -> JSONResponse:
    return JSONResponse(
        {
            "id": payload.get("id", "p-new"),
            "name": payload.get("name", "Unnamed"),
            "price": payload.get("price", 0),
        },
        status_code=201,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "broken" if BROKEN else "fixed"}
