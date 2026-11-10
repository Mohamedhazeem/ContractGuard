"""Offline request preflight use case."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..adapters.openapi import OpenApiRequestAdapter, make_openapi, validate_request
from ..adapters.spec_loader import resolve_operation
from ..domain.errors import IncompleteInputError, PolicyError
from ..domain.ports import ServiceRepository
from ..domain.ports import SpecLoader as SpecLoaderPort

_PROTECTED_HEADERS = frozenset(
    {"authorization", "cookie", "proxy-authorization", "x-api-key", "api-key"}
)

_JSON_TYPE_NAMES = {
    type(None): "null",
    bool: "boolean",
    int: "integer",
    float: "number",
    str: "string",
    list: "array",
    dict: "object",
}


@dataclass
class PreflightResult:
    """Result of an offline request preflight."""

    verdict: str
    service_id: str
    operation_id: str
    method: str
    path: str
    request_sent: bool = False
    violations: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "service_id": self.service_id,
            "operation_id": self.operation_id,
            "method": self.method,
            "path": self.path,
            "request_sent": self.request_sent,
            "violations": self.violations,
        }


def _json_type_name(value: Any) -> str:
    for typ, name in _JSON_TYPE_NAMES.items():
        if isinstance(value, typ):
            # bool is a subclass of int; check bool first (dict order handles this)
            return name
    return type(value).__name__


def _normalize_request_errors(
    errors: list[Any],
    *,
    operation_id: str,
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    for error in errors:
        cause = getattr(error, "__cause__", None)
        schema_errors = getattr(cause, "schema_errors", ()) if cause is not None else ()
        if schema_errors:
            for schema_error in schema_errors:
                violations.extend(_normalize_schema_error(schema_error, operation_id))
            continue

        # Parameter, body presence, or media type errors.
        message = str(getattr(error, "message", error))
        lower = message.lower()
        if "media type" in lower or "content type" in lower:
            code = "REQUEST_MEDIA_TYPE_UNDECLARED"
        elif "missing" in lower and "body" in lower:
            code = "REQUEST_REQUIRED_PROPERTY_MISSING"
        elif "missing" in lower:
            code = "REQUEST_PARAMETER_MISSING"
        else:
            code = "REQUEST_SCHEMA_TYPE_MISMATCH"

        json_pointer = getattr(error, "json_path", None) or "$"
        violations.append(
            {
                "code": code,
                "json_pointer": json_pointer,
                "message": message,
            }
        )
    return violations


def _normalize_schema_error(schema_error: Any, operation_id: str) -> list[dict[str, Any]]:
    validator = getattr(schema_error, "validator", None)
    message = getattr(schema_error, "message", str(schema_error))
    json_path = getattr(schema_error, "json_path", None) or "$"

    if validator == "required":
        match = re.search(r"'([^']+)' is a required property", message)
        property_name = match.group(1) if match else None
        if property_name:
            json_path = f"$.{property_name}"
        return [
            {
                "code": "REQUEST_REQUIRED_PROPERTY_MISSING",
                "json_pointer": json_path,
                "message": (
                    f"Missing required property: {property_name}" if property_name else message
                ),
            }
        ]

    if validator == "additionalProperties":
        pattern = r"Additional properties are not allowed \('([^']+)' was unexpected\)"
        match = re.search(pattern, message)
        property_name = match.group(1) if match else None
        if property_name:
            json_path = f"$.{property_name}"
        return [
            {
                "code": "REQUEST_SCHEMA_TYPE_MISMATCH",
                "json_pointer": json_path,
                "message": message,
            }
        ]

    if validator == "type":
        expected = getattr(schema_error, "validator_value", None)
        actual = _json_type_name(getattr(schema_error, "instance", None))
        return [
            {
                "code": "REQUEST_SCHEMA_TYPE_MISMATCH",
                "json_pointer": json_path,
                "message": message,
                "expected": expected,
                "actual": actual,
            }
        ]

    if validator == "enum":
        return [
            {
                "code": "REQUEST_ENUM_VALUE_INVALID",
                "json_pointer": json_path,
                "message": message,
                "expected": getattr(schema_error, "validator_value", None),
                "actual": getattr(schema_error, "instance", None),
            }
        ]

    return [
        {
            "code": "REQUEST_SCHEMA_TYPE_MISMATCH",
            "json_pointer": json_path,
            "message": message,
        }
    ]


def run_preflight(
    *,
    loader: SpecLoaderPort,
    service_repository: ServiceRepository,
    service_id: str,
    operation_id: str,
    path_params: dict[str, Any] | None,
    query_params: dict[str, Any] | None,
    headers: dict[str, str] | None,
    body: Any,
    content_type: str | None,
    max_body_bytes: int,
) -> PreflightResult:
    """Validate a proposed request without sending it."""
    service = service_repository.get(service_id)
    if service is None:
        raise IncompleteInputError(f"Service {service_id!r} is not registered.")

    loaded = loader.load_file(Path(service.spec_path))
    resolved = resolve_operation(loaded.document, operation_id)
    if resolved is None:
        raise IncompleteInputError(f"Operation {operation_id!r} was not found in the spec.")

    method, path_template, operation = resolved

    path_params = dict(path_params or {})
    query_params = dict(query_params or {})
    headers = dict(headers or {})

    # Protected headers are never accepted from model-supplied arguments.
    for name in headers:
        if name.lower() in _PROTECTED_HEADERS:
            raise PolicyError(f"Protected header is not allowed: {name}")

    # Declared parameters only.
    raw_params = operation.get("parameters", [])
    declared = [
        param
        for param in (raw_params if isinstance(raw_params, list) else [])
        if isinstance(param, dict) and "name" in param
    ]
    declared_by_name = {str(param["name"]): param for param in declared}
    for provided in list(path_params) + list(query_params) + list(headers):
        if provided not in declared_by_name:
            raise IncompleteInputError(f"Parameter {provided!r} is not declared by the operation.")

    # Required path parameters must be supplied.
    for param in declared:
        if param.get("in") == "path" and param.get("required") is True:
            name = str(param["name"])
            if name not in path_params:
                raise IncompleteInputError(f"Required path parameter {name!r} was not provided.")

    request_body = operation.get("requestBody")
    request_content = {}
    if isinstance(request_body, dict):
        content = request_body.get("content")
        request_content = content if isinstance(content, dict) else {}

    selected_content_type = (content_type or "").strip().lower()
    required_body = isinstance(request_body, dict) and request_body.get("required")
    needs_body = body is not None or required_body
    if needs_body and not selected_content_type:
        # Default to the first declared media type if only one exists.
        if len(request_content) == 1:
            selected_content_type = next(iter(request_content)).lower()
        else:
            raise IncompleteInputError("content_type must be provided for a request body.")

    allowed = {key.lower() for key in request_content}
    if selected_content_type and selected_content_type not in allowed:
        # Build a finding-style failure rather than raising.
        violation = {
            "code": "REQUEST_MEDIA_TYPE_UNDECLARED",
            "json_pointer": "$",
            "message": (
                f"Request media type {selected_content_type!r} is not declared by the operation."
            ),
        }
        return PreflightResult(
            verdict="FAIL",
            service_id=service_id,
            operation_id=operation_id,
            method=method,
            path=path_template,
            violations=[violation],
        )

    # Body size cap.
    body_bytes: bytes | None = None
    if body is not None:
        try:
            serialized = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise IncompleteInputError(f"Request body is not JSON-serializable: {exc}") from exc
        encoded = serialized.encode("utf-8")
        if len(encoded) > max_body_bytes:
            raise IncompleteInputError(f"Request body exceeds the {max_body_bytes}-byte limit.")
        body_bytes = encoded

    if body is not None and not request_content:
        raise IncompleteInputError("The operation does not declare a request body.")

    if isinstance(request_body, dict) and request_body.get("required") is True and body is None:
        raise IncompleteInputError("A request body is required by the operation.")

    # Build the actual path with substituted parameters.
    actual_path = path_template
    for name, value in path_params.items():
        actual_path = actual_path.replace(f"{{{name}}}", str(value))

    from openapi_core.datatypes import RequestParameters

    parameters = RequestParameters(
        path=path_params,
        query=query_params,
        header=headers,
    )

    host_url = service.base_url.rstrip("/")
    full_url_pattern = host_url + path_template

    request = OpenApiRequestAdapter(
        method=method,
        host_url=host_url,
        path=actual_path,
        full_url_pattern=full_url_pattern,
        parameters=parameters,
        body=body_bytes,
        content_type=selected_content_type,
    )

    openapi = make_openapi(loaded.document)
    errors = validate_request(openapi, request)
    violations = _normalize_request_errors(errors, operation_id=operation_id)

    verdict = "FAIL" if violations else "PASS"
    return PreflightResult(
        verdict=verdict,
        service_id=service_id,
        operation_id=operation_id,
        method=method,
        path=path_template,
        violations=violations,
    )
