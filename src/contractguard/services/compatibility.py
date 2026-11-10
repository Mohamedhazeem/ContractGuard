"""Compatibility ruleset for comparing two OpenAPI documents.

This module is pure: no I/O, no third-party dependencies. It resolves local
``$ref`` values and applies an explicit, versioned ruleset. Complex or
untested schema constructs are reported as ``unclassified`` rather than
guessed.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from ..domain.models import (
    ChangeClassification,
    CompatibilityFinding,
    FindingCode,
    Severity,
)

RULESET_VERSION = "1"

_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
_COMPOSITION_KEYWORDS = frozenset(
    {"oneOf", "anyOf", "allOf", "not", "if", "then", "else", "dependentSchemas"}
)


def dereference(document: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve local ``$ref`` values in a deep copy of ``document``.

    External references are rejected. Circular references are protected against.

    Raises:
        ValueError: If an external or unresolvable reference is encountered.
    """
    root = copy.deepcopy(document)
    cache: dict[str, Any] = {}

    def resolve(obj: Any, seen: frozenset[str]) -> Any:
        if isinstance(obj, dict):
            ref = obj.get("$ref")
            if isinstance(ref, str):
                if not ref.startswith("#"):
                    raise ValueError(f"External $ref is not allowed: {ref}")
                if ref in cache:
                    return copy.deepcopy(cache[ref])
                if ref in seen:
                    return obj
                target = _json_pointer_get(root, ref[1:])  # strip leading '#'
                resolved = resolve(target, seen | {ref})
                cache[ref] = resolved
                return copy.deepcopy(resolved)
            return {key: resolve(value, seen) for key, value in obj.items()}
        if isinstance(obj, list):
            return [resolve(value, seen) for value in obj]
        return obj

    resolved = resolve(root, frozenset())
    if not isinstance(resolved, dict):
        raise ValueError("OpenAPI document must be a JSON object")
    return resolved


def _escape_pointer(segment: str) -> str:
    return segment.replace("~", "~0").replace("/", "~1")


def diff_specs(
    baseline: Mapping[str, Any], candidate: Mapping[str, Any]
) -> list[CompatibilityFinding]:
    """Return classified findings comparing ``candidate`` to ``baseline``."""
    findings: list[CompatibilityFinding] = []
    raw_base_paths = baseline.get("paths")
    baseline_paths: dict[str, Any] = raw_base_paths if isinstance(raw_base_paths, dict) else {}
    raw_cand_paths = candidate.get("paths")
    candidate_paths: dict[str, Any] = raw_cand_paths if isinstance(raw_cand_paths, dict) else {}

    # Removed paths.
    for path in baseline_paths:
        if path not in candidate_paths:
            findings.append(
                CompatibilityFinding(
                    code=FindingCode.BASELINE_PATH_REMOVED,
                    classification=ChangeClassification.BREAKING,
                    severity=__import__("enum").Severity.ERROR if False else _severity("error"),
                    message=f"Path {path} was removed.",
                    path=path,
                    rationale="Existing operation is no longer available.",
                )
            )

    # Added paths.
    for path in candidate_paths:
        if path not in baseline_paths:
            findings.append(
                CompatibilityFinding(
                    code=FindingCode.BASELINE_PATH_ADDED,
                    classification=ChangeClassification.NON_BREAKING,
                    severity=_severity("info"),
                    message=f"Path {path} was added.",
                    path=path,
                    rationale="New optional operation; existing consumers are unaffected.",
                )
            )

    # Common paths.
    for path in baseline_paths:
        if path in candidate_paths:
            _diff_path(path, baseline_paths[path], candidate_paths[path], findings)

    # Top-level composition keywords.
    if _contains_composition(baseline) or _contains_composition(candidate):
        findings.append(
            CompatibilityFinding(
                code=FindingCode.UNCLASSIFIED_CHANGE,
                classification=ChangeClassification.UNCLASSIFIED,
                severity=_severity("warning"),
                message="Schema composition keywords are present in one of the contracts.",
                rationale="Complex composition is not classified by this ruleset version.",
            )
        )

    return findings


def _diff_path(
    path: str, base_item: Any, cand_item: Any, findings: list[CompatibilityFinding]
) -> None:
    base_item = base_item if isinstance(base_item, dict) else {}
    cand_item = cand_item if isinstance(cand_item, dict) else {}

    base_methods = {m for m in _METHODS if isinstance(base_item.get(m), dict)}
    cand_methods = {m for m in _METHODS if isinstance(cand_item.get(m), dict)}

    for method in sorted(base_methods - cand_methods):
        findings.append(
            CompatibilityFinding(
                code=FindingCode.BASELINE_OPERATION_REMOVED,
                classification=ChangeClassification.BREAKING,
                severity=_severity("error"),
                message=f"{method.upper()} {path} was removed.",
                method=method.upper(),
                path=path,
                rationale="Existing call is no longer supported.",
            )
        )

    for method in sorted(cand_methods - base_methods):
        findings.append(
            CompatibilityFinding(
                code=FindingCode.BASELINE_OPERATION_ADDED,
                classification=ChangeClassification.NON_BREAKING,
                severity=_severity("info"),
                message=f"{method.upper()} {path} was added.",
                method=method.upper(),
                path=path,
                rationale="New optional operation; existing consumers are unaffected.",
            )
        )

    for method in sorted(base_methods & cand_methods):
        _diff_operation(path, method.upper(), base_item[method], cand_item[method], findings)


def _diff_operation(
    path: str,
    method: str,
    base_op: dict[str, Any],
    cand_op: dict[str, Any],
    findings: list[CompatibilityFinding],
) -> None:
    operation_id = cand_op.get("operationId") or base_op.get("operationId")
    if isinstance(operation_id, str):
        pass
    else:
        operation_id = None

    # Responses.
    raw_base_responses = base_op.get("responses")
    base_responses: dict[str, Any] = (
        raw_base_responses if isinstance(raw_base_responses, dict) else {}
    )
    raw_cand_responses = cand_op.get("responses")
    cand_responses: dict[str, Any] = (
        raw_cand_responses if isinstance(raw_cand_responses, dict) else {}
    )

    for code in base_responses:
        if code not in cand_responses:
            findings.append(
                CompatibilityFinding(
                    code=FindingCode.BASELINE_RESPONSE_PROPERTY_REMOVED,
                    classification=ChangeClassification.BREAKING,
                    severity=_severity("error"),
                    message=f"Response status {code} was removed from {method} {path}.",
                    method=method,
                    path=path,
                    operation_id=operation_id,
                    json_pointer=f"#/paths/{_escape_pointer(path)}/responses/{code}",
                    rationale="Client's response case is no longer promised.",
                )
            )

    for code in cand_responses:
        if code not in base_responses:
            findings.append(
                CompatibilityFinding(
                    code=FindingCode.BASELINE_RESPONSE_PROPERTY_ADDED,
                    classification=ChangeClassification.NON_BREAKING,
                    severity=_severity("info"),
                    message=f"Response status {code} was added to {method} {path}.",
                    method=method,
                    path=path,
                    operation_id=operation_id,
                    json_pointer=f"#/paths/{_escape_pointer(path)}/responses/{code}",
                    rationale="Additional response case; existing consumers are unaffected.",
                )
            )

    for code in base_responses:
        if code in cand_responses:
            _diff_response(
                path,
                method,
                operation_id,
                code,
                base_responses[code],
                cand_responses[code],
                findings,
            )

    # Request body.
    base_body = base_op.get("requestBody")
    cand_body = cand_op.get("requestBody")
    if isinstance(base_body, dict) and not isinstance(cand_body, dict):
        findings.append(
            CompatibilityFinding(
                code=FindingCode.BASELINE_REQUEST_REQUIREMENT_ADDED,
                classification=ChangeClassification.BREAKING,
                severity=_severity("error"),
                message=f"Request body was removed from {method} {path}.",
                method=method,
                path=path,
                operation_id=operation_id,
                json_pointer=f"#/paths/{_escape_pointer(path)}/requestBody",
                rationale="Existing requests may be rejected.",
            )
        )
    elif isinstance(cand_body, dict) and not isinstance(base_body, dict):
        findings.append(
            CompatibilityFinding(
                code=FindingCode.BASELINE_REQUEST_PROPERTY_ADDED,
                classification=ChangeClassification.NON_BREAKING,
                severity=_severity("info"),
                message=f"Request body was added to {method} {path}.",
                method=method,
                path=path,
                operation_id=operation_id,
                json_pointer=f"#/paths/{_escape_pointer(path)}/requestBody",
                rationale="New capability; existing requests remain valid.",
            )
        )
    elif isinstance(base_body, dict) and isinstance(cand_body, dict):
        _diff_request_body(path, method, operation_id, base_body, cand_body, findings)

    # Parameters.
    raw_base_params = base_op.get("parameters")
    base_params: list[Any] = list(raw_base_params) if isinstance(raw_base_params, list) else []
    raw_cand_params = cand_op.get("parameters")
    cand_params: list[Any] = list(raw_cand_params) if isinstance(raw_cand_params, list) else []
    _diff_parameters(path, method, operation_id, base_params, cand_params, findings)


def _diff_response(
    path: str,
    method: str,
    operation_id: str | None,
    status_code: str,
    base_resp: dict[str, Any],
    cand_resp: dict[str, Any],
    findings: list[CompatibilityFinding],
) -> None:
    base_resp = base_resp if isinstance(base_resp, dict) else {}
    cand_resp = cand_resp if isinstance(cand_resp, dict) else {}

    raw_base_content = base_resp.get("content")
    base_content: dict[str, Any] = raw_base_content if isinstance(raw_base_content, dict) else {}
    raw_cand_content = cand_resp.get("content")
    cand_content: dict[str, Any] = raw_cand_content if isinstance(raw_cand_content, dict) else {}

    # Media types removed.
    for media in base_content:
        if media not in cand_content:
            findings.append(
                CompatibilityFinding(
                    code=FindingCode.BASELINE_RESPONSE_PROPERTY_REMOVED,
                    classification=ChangeClassification.BREAKING,
                    severity=_severity("error"),
                    message=(
                        f"Response media type {media} was removed from "
                        f"{method} {path} ({status_code})."
                    ),
                    method=method,
                    path=path,
                    operation_id=operation_id,
                    json_pointer=f"#/paths/{_escape_pointer(path)}/responses/{status_code}/content/{media}",
                    rationale="Client's response case is no longer promised.",
                )
            )

    # Schemas.
    for media in base_content:
        if media in cand_content:
            base_schema = _media_schema(base_content[media])
            cand_schema = _media_schema(cand_content[media])
            if base_schema is not None and cand_schema is not None:
                _diff_schema(
                    base_schema,
                    cand_schema,
                    json_pointer=f"#/paths/{_escape_pointer(path)}/responses/{status_code}/content/{media}/schema",
                    method=method,
                    path=path,
                    operation_id=operation_id,
                    context="response",
                    findings=findings,
                )


def _diff_request_body(
    path: str,
    method: str,
    operation_id: str | None,
    base_body: dict[str, Any],
    cand_body: dict[str, Any],
    findings: list[CompatibilityFinding],
) -> None:
    raw_base_content = base_body.get("content")
    base_content: dict[str, Any] = raw_base_content if isinstance(raw_base_content, dict) else {}
    raw_cand_content = cand_body.get("content")
    cand_content: dict[str, Any] = raw_cand_content if isinstance(raw_cand_content, dict) else {}

    for media in base_content:
        if media not in cand_content:
            findings.append(
                CompatibilityFinding(
                    code=FindingCode.BASELINE_RESPONSE_PROPERTY_REMOVED,
                    classification=ChangeClassification.BREAKING,
                    severity=_severity("error"),
                    message=f"Request media type {media} was removed from {method} {path}.",
                    method=method,
                    path=path,
                    operation_id=operation_id,
                    json_pointer=f"#/paths/{_escape_pointer(path)}/requestBody/content/{media}",
                    rationale="Existing requests may be rejected.",
                )
            )

    for media in base_content:
        if media in cand_content:
            base_schema = _media_schema(base_content[media])
            cand_schema = _media_schema(cand_content[media])
            if base_schema is not None and cand_schema is not None:
                _diff_schema(
                    base_schema,
                    cand_schema,
                    json_pointer=f"#/paths/{_escape_pointer(path)}/requestBody/content/{media}/schema",
                    method=method,
                    path=path,
                    operation_id=operation_id,
                    context="request",
                    findings=findings,
                )


def _diff_parameters(
    path: str,
    method: str,
    operation_id: str | None,
    base_params: list[Any],
    cand_params: list[Any],
    findings: list[CompatibilityFinding],
) -> None:
    base_by_name = {p.get("name"): p for p in base_params if isinstance(p, dict) and "name" in p}
    cand_by_name = {p.get("name"): p for p in cand_params if isinstance(p, dict) and "name" in p}

    for name in base_by_name:
        if name not in cand_by_name:
            findings.append(
                CompatibilityFinding(
                    code=FindingCode.BASELINE_REQUEST_REQUIREMENT_ADDED,
                    classification=ChangeClassification.POTENTIALLY_BREAKING,
                    severity=_severity("warning"),
                    message=f"Parameter {name} was removed from {method} {path}.",
                    method=method,
                    path=path,
                    operation_id=operation_id,
                    json_pointer=f"#/paths/{_escape_pointer(path)}/parameters",
                    rationale="Existing callers may send it; server behaviour is unclear.",
                )
            )

    for name in cand_by_name:
        if name not in base_by_name:
            param = cand_by_name[name]
            if param.get("required") is True:
                findings.append(
                    CompatibilityFinding(
                        code=FindingCode.BASELINE_REQUEST_REQUIREMENT_ADDED,
                        classification=ChangeClassification.BREAKING,
                        severity=_severity("error"),
                        message=f"Required parameter {name} was added to {method} {path}.",
                        method=method,
                        path=path,
                        operation_id=operation_id,
                        json_pointer=f"#/paths/{_escape_pointer(path)}/parameters",
                        rationale="Existing client requests may become invalid.",
                    )
                )
            else:
                findings.append(
                    CompatibilityFinding(
                        code=FindingCode.BASELINE_REQUEST_PROPERTY_ADDED,
                        classification=ChangeClassification.NON_BREAKING,
                        severity=_severity("info"),
                        message=f"Optional parameter {name} was added to {method} {path}.",
                        method=method,
                        path=path,
                        operation_id=operation_id,
                        json_pointer=f"#/paths/{_escape_pointer(path)}/parameters",
                        rationale="Existing requests remain valid.",
                    )
                )

    for name in base_by_name:
        if name in cand_by_name:
            base_param = base_by_name[name]
            cand_param = cand_by_name[name]
            # required transition
            if base_param.get("required") is not True and cand_param.get("required") is True:
                findings.append(
                    CompatibilityFinding(
                        code=FindingCode.BASELINE_REQUEST_REQUIREMENT_ADDED,
                        classification=ChangeClassification.BREAKING,
                        severity=_severity("error"),
                        message=f"Parameter {name} became required in {method} {path}.",
                        method=method,
                        path=path,
                        operation_id=operation_id,
                        json_pointer=f"#/paths/{_escape_pointer(path)}/parameters/{name}",
                        rationale="Existing callers may omit it.",
                    )
                )
            if base_param.get("required") is True and cand_param.get("required") is not True:
                findings.append(
                    CompatibilityFinding(
                        code=FindingCode.BASELINE_REQUEST_REQUIREMENT_ADDED,
                        classification=ChangeClassification.BREAKING,
                        severity=_severity("error"),
                        message=f"Parameter {name} became optional in {method} {path}.",
                        method=method,
                        path=path,
                        operation_id=operation_id,
                        json_pointer=f"#/paths/{_escape_pointer(path)}/parameters/{name}",
                        rationale=(
                            "Server no longer guarantees the input is required "
                            "(ambiguous contract)."
                        ),
                    )
                )
            # schema type/constraints
            base_schema = (
                base_param.get("schema") if isinstance(base_param.get("schema"), dict) else None
            )
            cand_schema = (
                cand_param.get("schema") if isinstance(cand_param.get("schema"), dict) else None
            )
            if base_schema is not None and cand_schema is not None:
                _diff_schema(
                    base_schema,
                    cand_schema,
                    json_pointer=f"#/paths/{_escape_pointer(path)}/parameters/{name}/schema",
                    method=method,
                    path=path,
                    operation_id=operation_id,
                    context="request",
                    findings=findings,
                )


def _diff_schema(
    base: dict[str, Any],
    cand: dict[str, Any],
    *,
    json_pointer: str,
    method: str,
    path: str,
    operation_id: str | None,
    context: str,
    findings: list[CompatibilityFinding],
) -> None:
    # Unclassified if composition present.
    if _contains_composition(base) or _contains_composition(cand):
        findings.append(
            CompatibilityFinding(
                code=FindingCode.UNCLASSIFIED_CHANGE,
                classification=ChangeClassification.UNCLASSIFIED,
                severity=_severity("warning"),
                message=f"Schema at {json_pointer} uses composition keywords.",
                method=method,
                path=path,
                operation_id=operation_id,
                json_pointer=json_pointer,
                rationale="Composition is not classified by this ruleset version.",
            )
        )
        return

    # Type change.
    base_type = base.get("type")
    cand_type = cand.get("type")
    if base_type is not None and cand_type is not None and base_type != cand_type:
        findings.append(
            CompatibilityFinding(
                code=FindingCode.BASELINE_SCHEMA_TYPE_CHANGED,
                classification=ChangeClassification.BREAKING,
                severity=_severity("error"),
                message=f"Type changed from {base_type} to {cand_type} at {json_pointer}.",
                method=method,
                path=path,
                operation_id=operation_id,
                json_pointer=json_pointer,
                old_value=str(base_type),
                new_value=str(cand_type),
                rationale="Client deserialization or logic may fail.",
            )
        )
        return  # don't recurse after incompatible type change

    # Nullable change: baseline not nullable, candidate nullable.
    base_nullable = _allows_null(base)
    cand_nullable = _allows_null(cand)
    if not base_nullable and cand_nullable:
        findings.append(
            CompatibilityFinding(
                code=FindingCode.BASELINE_SCHEMA_TYPE_CHANGED,
                classification=ChangeClassification.POTENTIALLY_BREAKING,
                severity=_severity("warning"),
                message=f"Field at {json_pointer} newly permits null.",
                method=method,
                path=path,
                operation_id=operation_id,
                json_pointer=json_pointer,
                rationale="Existing consumers may not handle null.",
            )
        )

    # Enum changes.
    base_enum = base.get("enum")
    cand_enum = cand.get("enum")
    if isinstance(base_enum, list) and isinstance(cand_enum, list):
        base_set = set(base_enum)
        cand_set = set(cand_enum)
        removed = base_set - cand_set
        added = cand_set - base_set
        if removed:
            code = (
                FindingCode.BASELINE_REQUEST_REQUIREMENT_ADDED
                if context == "request"
                else FindingCode.BASELINE_SCHEMA_TYPE_CHANGED
            )
            findings.append(
                CompatibilityFinding(
                    code=code,
                    classification=ChangeClassification.BREAKING,
                    severity=_severity("error"),
                    message=f"Enum values removed at {json_pointer}: {sorted(removed, key=str)}.",
                    method=method,
                    path=path,
                    operation_id=operation_id,
                    json_pointer=json_pointer,
                    rationale="Previously valid input becomes invalid.",
                )
            )
        if added:
            findings.append(
                CompatibilityFinding(
                    code=FindingCode.BASELINE_PROPERTY_ADDED,
                    classification=ChangeClassification.NON_BREAKING,
                    severity=_severity("info"),
                    message=f"Enum values added at {json_pointer}: {sorted(added, key=str)}.",
                    method=method,
                    path=path,
                    operation_id=operation_id,
                    json_pointer=json_pointer,
                    rationale="Widening accepted values is non-breaking.",
                )
            )

    # Constraints stricter.
    _diff_constraints(base, cand, json_pointer, method, path, operation_id, context, findings)

    # Required arrays.
    base_required = (
        set(base.get("required", [])) if isinstance(base.get("required"), list) else set()
    )
    cand_required = (
        set(cand.get("required", [])) if isinstance(cand.get("required"), list) else set()
    )

    base_props = base.get("properties") if isinstance(base.get("properties"), dict) else None
    cand_props = cand.get("properties") if isinstance(cand.get("properties"), dict) else None

    if base_props is not None or cand_props is not None:
        base_props = base_props or {}
        cand_props = cand_props or {}

        # Removed properties.
        for name in base_props:
            if name not in cand_props:
                if context == "response":
                    findings.append(
                        CompatibilityFinding(
                            code=FindingCode.BASELINE_RESPONSE_PROPERTY_REMOVED,
                            classification=ChangeClassification.BREAKING,
                            severity=_severity("error"),
                            message=f"Response property {name} was removed at {json_pointer}.",
                            method=method,
                            path=path,
                            operation_id=operation_id,
                            json_pointer=f"{json_pointer}/properties/{name}",
                            rationale="Client may read that property.",
                        )
                    )
                else:
                    findings.append(
                        CompatibilityFinding(
                            code=FindingCode.BASELINE_REQUEST_REQUIREMENT_ADDED,
                            classification=ChangeClassification.POTENTIALLY_BREAKING,
                            severity=_severity("warning"),
                            message=f"Request property {name} was removed at {json_pointer}.",
                            method=method,
                            path=path,
                            operation_id=operation_id,
                            json_pointer=f"{json_pointer}/properties/{name}",
                            rationale="Existing requests sending it may be rejected.",
                        )
                    )

        # Added properties.
        for name in cand_props:
            if name not in base_props:
                code = (
                    FindingCode.BASELINE_REQUEST_PROPERTY_ADDED
                    if context == "request"
                    else FindingCode.BASELINE_RESPONSE_PROPERTY_ADDED
                )
                findings.append(
                    CompatibilityFinding(
                        code=code,
                        classification=ChangeClassification.NON_BREAKING,
                        severity=_severity("info"),
                        message=f"Property {name} was added at {json_pointer}.",
                        method=method,
                        path=path,
                        operation_id=operation_id,
                        json_pointer=f"{json_pointer}/properties/{name}",
                        rationale="New field; existing consumers are unaffected.",
                    )
                )

        # Required transitions.
        for name in base_props:
            if name in cand_props:
                if name in base_required and name not in cand_required and context == "response":
                    findings.append(
                        CompatibilityFinding(
                            code=FindingCode.BASELINE_RESPONSE_PROPERTY_REMOVED,
                            classification=ChangeClassification.BREAKING,
                            severity=_severity("error"),
                            message=(
                                f"Response property {name} became optional at {json_pointer}."
                            ),
                            method=method,
                            path=path,
                            operation_id=operation_id,
                            json_pointer=f"{json_pointer}/properties/{name}",
                            rationale="Server no longer guarantees presence.",
                        )
                    )
                if name not in base_required and name in cand_required:
                    if context == "request":
                        findings.append(
                            CompatibilityFinding(
                                code=FindingCode.BASELINE_REQUEST_REQUIREMENT_ADDED,
                                classification=ChangeClassification.BREAKING,
                                severity=_severity("error"),
                                message=(
                                    f"Request property {name} became required at {json_pointer}."
                                ),
                                method=method,
                                path=path,
                                operation_id=operation_id,
                                json_pointer=f"{json_pointer}/properties/{name}",
                                rationale="Existing requests may be rejected.",
                            )
                        )
                    else:
                        findings.append(
                            CompatibilityFinding(
                                code=FindingCode.BASELINE_RESPONSE_PROPERTY_ADDED,
                                classification=ChangeClassification.NON_BREAKING,
                                severity=_severity("info"),
                                message=(
                                    f"Response property {name} became required at {json_pointer}."
                                ),
                                method=method,
                                path=path,
                                operation_id=operation_id,
                                json_pointer=f"{json_pointer}/properties/{name}",
                                rationale="Stronger guarantee; existing consumers are unaffected.",
                            )
                        )

        # Recurse into common properties.
        for name in base_props:
            if name in cand_props:
                _diff_schema(
                    base_props[name] if isinstance(base_props[name], dict) else {},
                    cand_props[name] if isinstance(cand_props[name], dict) else {},
                    json_pointer=f"{json_pointer}/properties/{name}",
                    method=method,
                    path=path,
                    operation_id=operation_id,
                    context=context,
                    findings=findings,
                )

    # items (arrays)
    base_items = base.get("items")
    cand_items = cand.get("items")
    if isinstance(base_items, dict) and isinstance(cand_items, dict):
        _diff_schema(
            base_items,
            cand_items,
            json_pointer=f"{json_pointer}/items",
            method=method,
            path=path,
            operation_id=operation_id,
            context=context,
            findings=findings,
        )


def _diff_constraints(
    base: dict[str, Any],
    cand: dict[str, Any],
    json_pointer: str,
    method: str,
    path: str,
    operation_id: str | None,
    context: str,
    findings: list[CompatibilityFinding],
) -> None:
    # minLength increased
    if "minLength" in base and "minLength" in cand and cand["minLength"] > base["minLength"]:
        findings.append(
            _constraint_finding("minLength increased", json_pointer, method, path, operation_id)
        )
    if "maxLength" in base and "maxLength" in cand and cand["maxLength"] < base["maxLength"]:
        findings.append(
            _constraint_finding("maxLength decreased", json_pointer, method, path, operation_id)
        )
    if "minimum" in base and "minimum" in cand and cand["minimum"] > base["minimum"]:
        findings.append(
            _constraint_finding("minimum increased", json_pointer, method, path, operation_id)
        )
    if "maximum" in base and "maximum" in cand and cand["maximum"] < base["maximum"]:
        findings.append(
            _constraint_finding("maximum decreased", json_pointer, method, path, operation_id)
        )
    if "minItems" in base and "minItems" in cand and cand["minItems"] > base["minItems"]:
        findings.append(
            _constraint_finding("minItems increased", json_pointer, method, path, operation_id)
        )
    if "maxItems" in base and "maxItems" in cand and cand["maxItems"] < base["maxItems"]:
        findings.append(
            _constraint_finding("maxItems decreased", json_pointer, method, path, operation_id)
        )


def _constraint_finding(
    description: str,
    json_pointer: str,
    method: str,
    path: str,
    operation_id: str | None,
) -> CompatibilityFinding:
    return CompatibilityFinding(
        code=FindingCode.BASELINE_REQUEST_REQUIREMENT_ADDED,
        classification=ChangeClassification.POTENTIALLY_BREAKING,
        severity=_severity("warning"),
        message=f"Constraint tightened at {json_pointer}: {description}.",
        method=method,
        path=path,
        operation_id=operation_id,
        json_pointer=json_pointer,
        rationale="Existing client values may fail.",
    )


def _media_schema(media: Any) -> dict[str, Any] | None:
    if not isinstance(media, dict):
        return None
    schema = media.get("schema")
    return schema if isinstance(schema, dict) else None


def _contains_composition(obj: Any) -> bool:
    if isinstance(obj, dict):
        if any(key in obj for key in _COMPOSITION_KEYWORDS):
            return True
        return any(_contains_composition(value) for value in obj.values())
    if isinstance(obj, list):
        return any(_contains_composition(value) for value in obj)
    return False


def _allows_null(schema: dict[str, Any]) -> bool:
    if schema.get("nullable") is True:
        return True
    t = schema.get("type")
    return bool(isinstance(t, list) and "null" in t)


def _severity(value: str) -> Severity:
    return Severity(value)


def _json_pointer_get(document: Any, pointer: str) -> Any:
    if pointer == "" or pointer == "/":
        return document
    parts = pointer.split("/")
    # first part empty (leading slash)
    if parts and parts[0] == "":
        parts = parts[1:]
    current = document
    for part in parts:
        key = part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if key not in current:
                raise ValueError(f"Unresolvable $ref: {pointer}")
            current = current[key]
        elif isinstance(current, list):
            try:
                index = int(key)
            except ValueError as exc:
                raise ValueError(f"Unresolvable $ref: {pointer}") from exc
            if index < 0 or index >= len(current):
                raise ValueError(f"Unresolvable $ref: {pointer}")
            current = current[index]
        else:
            raise ValueError(f"Unresolvable $ref: {pointer}")
    return current
