"""Safe live response verification use case."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..adapters.http_transport import HttpxTransport
from ..adapters.openapi import (
    OpenApiRequestAdapter,
    OpenApiResponseAdapter,
    make_openapi,
    validate_request,
    validate_response,
)
from ..adapters.spec_loader import resolve_operation
from ..domain.errors import IncompleteInputError, NotFoundError
from ..domain.models import HttpRequest
from ..domain.ports import ServiceRepository
from ..domain.ports import SpecLoader as SpecLoaderPort

_JSON_TYPE_NAMES = {
    type(None): "null",
    bool: "boolean",
    int: "number",
    float: "number",
    str: "string",
    list: "array",
    dict: "object",
}


@dataclass
class LiveTestResult:
    """Result of one live response verification."""

    verdict: str
    service_id: str
    operation_id: str
    method: str
    path: str
    request_sent: bool = False
    status_code: int | None = None
    content_type: str | None = None
    response_bytes: int = 0
    duration_ms: int = 0
    violations: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "service_id": self.service_id,
            "operation_id": self.operation_id,
            "method": self.method,
            "path": self.path,
            "request_sent": self.request_sent,
            "status_code": self.status_code,
            "content_type": self.content_type,
            "response_bytes": self.response_bytes,
            "duration_ms": self.duration_ms,
            "violations": self.violations,
        }


def _json_type_name(value: Any) -> str:
    for typ, name in _JSON_TYPE_NAMES.items():
        if isinstance(value, typ):
            return name
    return type(value).__name__


def _normalize_request_errors(errors: list[Any], *, operation_id: str) -> list[dict[str, Any]]:
    from ..services.preflight import _normalize_request_errors as normalize

    return normalize(errors, operation_id=operation_id)


def _normalize_response_errors(errors: list[Any], *, operation_id: str) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    for error in errors:
        name = type(error).__name__
        message = str(getattr(error, "message", error))
        if name == "ResponseNotFound" or "Unknown response" in message:
            violations.append(
                {"code": "RESPONSE_STATUS_UNDECLARED", "json_pointer": "$", "message": message}
            )
            continue

        cause = getattr(error, "__cause__", None)
        schema_errors = getattr(cause, "schema_errors", ()) if cause is not None else ()
        if schema_errors:
            for schema_error in schema_errors:
                validator = getattr(schema_error, "validator", None)
                json_path = getattr(schema_error, "json_path", None) or "$"
                if validator == "required":
                    pattern = r"'([^']+)' is a required property"
                    message = getattr(schema_error, "message", "")
                    match = re.search(pattern, message)
                    prop = match.group(1) if match else None
                    if prop:
                        json_path = f"$.{prop}"
                    violations.append(
                        {
                            "code": "RESPONSE_REQUIRED_PROPERTY_MISSING",
                            "json_pointer": json_path,
                            "message": getattr(schema_error, "message", str(schema_error)),
                        }
                    )
                elif validator == "type":
                    violations.append(
                        {
                            "code": "RESPONSE_SCHEMA_TYPE_MISMATCH",
                            "json_pointer": json_path,
                            "message": getattr(schema_error, "message", str(schema_error)),
                            "expected": getattr(schema_error, "validator_value", None),
                            "actual": _json_type_name(getattr(schema_error, "instance", None)),
                        }
                    )
                else:
                    violations.append(
                        {
                            "code": "RESPONSE_SCHEMA_TYPE_MISMATCH",
                            "json_pointer": json_path,
                            "message": getattr(schema_error, "message", str(schema_error)),
                        }
                    )
            continue

        lower = message.lower()
        if "mimetype" in lower or "media type" in lower or "content for the following" in lower:
            violations.append(
                {"code": "RESPONSE_MEDIA_TYPE_UNDECLARED", "json_pointer": "$", "message": message}
            )
        else:
            violations.append(
                {"code": "RESPONSE_SCHEMA_TYPE_MISMATCH", "json_pointer": "$", "message": message}
            )
    return violations


def run_live_test(
    *,
    loader: SpecLoaderPort,
    service_repository: ServiceRepository,
    transport: HttpxTransport,
    service_id: str,
    operation_id: str,
    path_params: dict[str, Any] | None,
    query_params: dict[str, Any] | None,
    timeout_seconds: float,
    max_response_bytes: int,
) -> LiveTestResult:
    service = service_repository.get(service_id)
    if service is None:
        raise NotFoundError(f"Service {service_id!r} is not registered.")

    loaded = loader.load_file(Path(service.spec_path))
    resolved = resolve_operation(loaded.document, operation_id)
    if resolved is None:
        raise IncompleteInputError(f"Operation {operation_id!r} was not found in the spec.")

    method, path_template, operation = resolved

    if method not in {"GET", "HEAD"}:
        return LiveTestResult(
            verdict="BLOCKED",
            service_id=service_id,
            operation_id=operation_id,
            method=method,
            path=path_template,
            request_sent=False,
            violations=[
                {
                    "code": "LIVE_METHOD_BLOCKED",
                    "json_pointer": "$",
                    "message": (
                        f"Live execution of {method} is blocked in the MVP; use preflight instead."
                    ),
                }
            ],
        )

    path_params = dict(path_params or {})
    query_params = dict(query_params or {})

    raw_params = operation.get("parameters", [])
    candidates = raw_params if isinstance(raw_params, list) else []
    for param in candidates:
        if isinstance(param, dict) and param.get("in") == "path" and param.get("required") is True:
            name = str(param.get("name"))
            if name not in path_params:
                raise IncompleteInputError(f"Required path parameter {name!r} was not provided.")

    actual_path = path_template
    for name, value in path_params.items():
        actual_path = actual_path.replace(f"{{{name}}}", str(value))

    from openapi_core.datatypes import RequestParameters

    parameters = RequestParameters(path=path_params, query=query_params, header={})
    host_url = service.base_url.rstrip("/")
    full_url_pattern = host_url + path_template

    request = OpenApiRequestAdapter(
        method=method,
        host_url=host_url,
        path=actual_path,
        full_url_pattern=full_url_pattern,
        parameters=parameters,
        body=None,
        content_type="",
    )

    openapi = make_openapi(loaded.document, base_url=service.base_url)
    request_errors = validate_request(openapi, request)
    if request_errors:
        violations = _normalize_request_errors(request_errors, operation_id=operation_id)
        return LiveTestResult(
            verdict="FAIL",
            service_id=service_id,
            operation_id=operation_id,
            method=method,
            path=path_template,
            request_sent=False,
            violations=violations,
        )

    http_request = HttpRequest(method=method, url=host_url + actual_path, headers={}, body=None)
    response = transport.send(http_request, timeout_seconds=timeout_seconds)

    content_type = response.headers.get("content-type", "")
    content_type = content_type or response.headers.get("Content-Type", "")
    response_adapter = OpenApiResponseAdapter(
        status_code=response.status_code,
        headers=response.headers,
        content_type=content_type if content_type else "application/octet-stream",
        data=response.body,
    )

    if 300 <= response.status_code < 400:
        location = response.headers.get("location", "")
        return LiveTestResult(
            verdict="INCOMPLETE",
            service_id=service_id,
            operation_id=operation_id,
            method=method,
            path=path_template,
            request_sent=True,
            status_code=response.status_code,
            content_type=content_type or None,
            response_bytes=len(response.body),
            duration_ms=response.elapsed_ms,
            violations=[
                {
                    "code": "TRANSPORT_ERROR",
                    "json_pointer": "$",
                    "message": (
                        f"Redirect not followed (HTTP {response.status_code}); Location: {location}"
                    ),
                }
            ],
        )

    response_errors = validate_response(openapi, request, response_adapter)
    violations = _normalize_response_errors(response_errors, operation_id=operation_id)

    verdict = "FAIL" if violations else "PASS"
    return LiveTestResult(
        verdict=verdict,
        service_id=service_id,
        operation_id=operation_id,
        method=method,
        path=path_template,
        request_sent=True,
        status_code=response.status_code,
        content_type=content_type or None,
        response_bytes=len(response.body),
        duration_ms=response.elapsed_ms,
        violations=violations,
    )
