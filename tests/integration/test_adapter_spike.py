"""Slice 0 adapter spike: prove the openapi-core integration.

These tests are the GO/NO-GO gate for the project. They use the real
``openapi-core`` engine and the project's own adapter classes, not mocks.
"""

from __future__ import annotations

import json

import pytest
from openapi_core.datatypes import RequestParameters
from openapi_core.protocols import Request as OpenApiRequestProtocol
from openapi_core.protocols import Response as OpenApiResponseProtocol

from contractguard.adapters.openapi import (
    OpenApiRequestAdapter,
    OpenApiResponseAdapter,
    make_openapi,
    validate_request,
    validate_response,
)

SPEC = {
    "openapi": "3.0.3",
    "info": {"title": "Adapter spike", "version": "1.0.0"},
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


@pytest.mark.integration
def test_request_adapter_satisfies_protocol() -> None:
    adapter = OpenApiRequestAdapter(
        method="POST",
        host_url="http://127.0.0.1:8000",
        path="/products",
        full_url_pattern="http://127.0.0.1:8000/products",
        parameters=RequestParameters(),
        body=None,
        content_type="application/json",
    )
    assert isinstance(adapter, OpenApiRequestProtocol)


@pytest.mark.integration
def test_response_adapter_satisfies_protocol() -> None:
    adapter = OpenApiResponseAdapter(
        status_code=200,
        headers={},
        content_type="application/json",
        data=b"{}",
    )
    assert isinstance(adapter, OpenApiResponseProtocol)


@pytest.mark.integration
def test_request_preflight_collects_every_missing_property() -> None:
    openapi = make_openapi(SPEC)
    request = OpenApiRequestAdapter(
        method="POST",
        host_url="http://127.0.0.1:8000",
        path="/products",
        full_url_pattern="http://127.0.0.1:8000/products",
        parameters=RequestParameters(),
        body=json.dumps({"invalid": "json"}).encode("utf-8"),
        content_type="application/json",
    )

    errors = validate_request(openapi, request)

    assert len(errors) == 1
    schema_errors = getattr(errors[0].__cause__, "schema_errors", ())
    assert len(schema_errors) == 3
    messages = " ".join(str(error) for error in schema_errors)
    assert "'id' is a required property" in messages
    assert "'name' is a required property" in messages
    assert "'price' is a required property" in messages


@pytest.mark.integration
def test_live_response_reports_price_type_mismatch() -> None:
    openapi = make_openapi(SPEC)
    request = OpenApiRequestAdapter(
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

    errors = validate_response(openapi, request, response)

    assert len(errors) == 1
    schema_errors = getattr(errors[0].__cause__, "schema_errors", ())
    assert any("not of type 'number'" in str(error) for error in schema_errors)
