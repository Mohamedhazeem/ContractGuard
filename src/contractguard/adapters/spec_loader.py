"""Spec loading, structural validation, and operation indexing.

This adapter owns all OpenAPI document I/O and all third-party validation calls.
It implements :class:`contractguard.domain.ports.SpecLoader`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import DEFAULT_MAX_SPEC_BYTES
from ..domain.errors import SpecLoadError, SpecValidationError, UnsupportedSpecError
from ..domain.models import (
    InspectionReport,
    LoadedSpec,
    Operation,
    OperationDetail,
    SpecSnapshot,
    canonical_json_bytes,
    sha256_hex,
)


@dataclass
class _Analysis:
    status: str
    document: Mapping[str, Any] | None
    snapshot: SpecSnapshot | None
    errors: tuple[str, ...]
    report: InspectionReport


_SUPPORTED_VERSION_PREFIXES = ("3.0.", "3.1.", "3.2.")
_COMPOSITION_KEYWORDS = frozenset(
    {"oneOf", "anyOf", "allOf", "not", "if", "then", "else", "dependentSchemas"}
)


class SpecLoader:
    """Load, validate, and index local OpenAPI documents."""

    def __init__(self, max_spec_bytes: int = DEFAULT_MAX_SPEC_BYTES) -> None:
        if max_spec_bytes < 1:
            raise ValueError("max_spec_bytes must be positive")
        self._max_spec_bytes = max_spec_bytes

    def inspect(self, path: Path) -> InspectionReport:
        limit = self._max_spec_bytes
        return self._analyze(path, limit).report

    def load_file(self, path: Path) -> LoadedSpec:
        analysis = self._analyze(path, self._max_spec_bytes)
        if analysis.status != "VALID":
            if analysis.status == "UNSUPPORTED":
                message = "; ".join(analysis.errors) or "Unsupported OpenAPI document"
                raise UnsupportedSpecError(message)
            message = "; ".join(analysis.errors) or "Invalid OpenAPI document"
            raise SpecValidationError(message)
        if analysis.document is None or analysis.snapshot is None:
            raise SpecLoadError("Spec analysis did not produce a document")
        return LoadedSpec(snapshot=analysis.snapshot, document=analysis.document)

    def load_document(self, document: Mapping[str, Any], *, source_name: str) -> LoadedSpec:
        # Minimal support: validate structure and build snapshot without file I/O.
        version = document.get("openapi") if isinstance(document, Mapping) else None
        if not isinstance(version, str) or not version.startswith(_SUPPORTED_VERSION_PREFIXES):
            raise UnsupportedSpecError(f"Unsupported OpenAPI version: {version!r}")
        try:
            from jsonschema_path import SchemaPath
            from openapi_spec_validator.shortcuts import get_validator_cls

            validator_cls = get_validator_cls(document)
        except Exception as exc:
            raise UnsupportedSpecError(f"Unsupported OpenAPI document: {exc}") from exc
        validator = validator_cls(SchemaPath.from_dict(document))
        errors = [
            f"{getattr(err, 'message', str(err))} (at {getattr(err, 'json_path', None) or '$'})"
            for err in validator.iter_errors()
        ]
        if errors:
            raise SpecValidationError("; ".join(errors))
        external = _external_refs(document)
        if external:
            joined = ", ".join(sorted(set(external)))
            raise SpecValidationError("External $ref is not allowed: " + joined)
        _operations, operation_models, _gaps, _unsupported = _build_operations(document)
        info = document.get("info", {}) if isinstance(document.get("info"), Mapping) else {}
        title = info.get("title", "") if isinstance(info, Mapping) else ""
        api_version = info.get("version", "") if isinstance(info, Mapping) else ""
        snapshot = SpecSnapshot(
            sha256=sha256_hex(canonical_json_bytes(document)),
            openapi_version=version,
            title=title or "<untitled>",
            api_version=api_version or "<unversioned>",
            operations=tuple(operation_models),
            source_name=source_name,
        )
        return LoadedSpec(snapshot=snapshot, document=document)

    def _analyze(self, path: Path, limit: int) -> _Analysis:
        import yaml

        try:
            stat = path.stat()
        except OSError as exc:
            report = _report(
                status="INVALID_SPEC",
                spec_path=str(path),
                sha256="",
                openapi_version="",
                title="",
                api_version="",
                operations=(),
                errors=(f"Cannot read spec file: {exc}",),
                coverage_gaps=(),
                unsupported_constructs=(),
            )
            return _Analysis("INVALID_SPEC", None, None, report.errors, report)

        if stat.st_size > limit:
            report = _report(
                status="INVALID_SPEC",
                spec_path=str(path),
                sha256="",
                openapi_version="",
                title="",
                api_version="",
                operations=(),
                errors=(f"Spec file exceeds the size limit of {limit} bytes",),
                coverage_gaps=(),
                unsupported_constructs=(),
            )
            return _Analysis("INVALID_SPEC", None, None, report.errors, report)

        try:
            raw = path.read_bytes()
            text = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            report = _report(
                status="INVALID_SPEC",
                spec_path=str(path),
                sha256="",
                openapi_version="",
                title="",
                api_version="",
                operations=(),
                errors=(f"Cannot read spec file: {exc}",),
                coverage_gaps=(),
                unsupported_constructs=(),
            )
            return _Analysis("INVALID_SPEC", None, None, report.errors, report)

        # --- Parsing ---
        try:
            document = json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
        except (json.JSONDecodeError, yaml.YAMLError) as exc:
            report = _report(
                status="INVALID_SPEC",
                spec_path=str(path),
                sha256="",
                openapi_version="",
                title="",
                api_version="",
                operations=(),
                errors=(f"Cannot parse spec file: {exc}",),
                coverage_gaps=(),
                unsupported_constructs=(),
            )
            return _Analysis("INVALID_SPEC", None, None, report.errors, report)

        if not isinstance(document, dict):
            report = _report(
                status="INVALID_SPEC",
                spec_path=str(path),
                sha256="",
                openapi_version="",
                title="",
                api_version="",
                operations=(),
                errors=("Spec file must contain a JSON or YAML object",),
                coverage_gaps=(),
                unsupported_constructs=(),
            )
            return _Analysis("INVALID_SPEC", None, None, report.errors, report)

        # --- External $ref blocking ---
        external = _external_refs(document)
        if external:
            errors = tuple(f"External $ref is not allowed: {ref}" for ref in sorted(set(external)))
            report = _report(
                status="INVALID_SPEC",
                spec_path=str(path),
                sha256="",
                openapi_version=str(document.get("openapi", "")),
                title="",
                api_version="",
                operations=(),
                errors=errors,
                coverage_gaps=(),
                unsupported_constructs=(),
            )
            return _Analysis("INVALID_SPEC", None, None, report.errors, report)

        version = document.get("openapi")
        if not isinstance(version, str) or not version.startswith(_SUPPORTED_VERSION_PREFIXES):
            report = _report(
                status="UNSUPPORTED",
                spec_path=str(path),
                sha256="",
                openapi_version=str(version) if version is not None else "",
                title="",
                api_version="",
                operations=(),
                errors=(f"Unsupported OpenAPI version: {version!r}",),
                coverage_gaps=(),
                unsupported_constructs=(),
            )
            return _Analysis("UNSUPPORTED", None, None, report.errors, report)

        # --- Structural validation ---
        try:
            from jsonschema_path import SchemaPath
            from openapi_spec_validator.shortcuts import get_validator_cls

            validator_cls = get_validator_cls(document)
        except Exception as exc:
            report = _report(
                status="UNSUPPORTED",
                spec_path=str(path),
                sha256="",
                openapi_version=version,
                title="",
                api_version="",
                operations=(),
                errors=(f"Unsupported OpenAPI document: {exc}",),
                coverage_gaps=(),
                unsupported_constructs=(),
            )
            return _Analysis("UNSUPPORTED", None, None, report.errors, report)

        validator = validator_cls(SchemaPath.from_dict(document))
        validation_errors = list(validator.iter_errors())
        if validation_errors:
            errors = tuple(
                f"{getattr(err, 'message', str(err))} (at {getattr(err, 'json_path', None) or '$'})"
                for err in validation_errors
            )
            info = document.get("info", {}) if isinstance(document.get("info"), Mapping) else {}
            title = info.get("title", "") if isinstance(info, Mapping) else ""
            api_version = info.get("version", "") if isinstance(info, Mapping) else ""
            report = _report(
                status="INVALID_SPEC",
                spec_path=str(path),
                sha256="",
                openapi_version=version,
                title=title or "<untitled>",
                api_version=api_version or "<unversioned>",
                operations=(),
                errors=errors,
                coverage_gaps=(),
                unsupported_constructs=(),
            )
            return _Analysis("INVALID_SPEC", None, None, report.errors, report)

        operations_detail, operation_models, gaps, unsupported = _build_operations(document)

        info = document.get("info", {}) if isinstance(document.get("info"), Mapping) else {}
        title = info.get("title", "") if isinstance(info, Mapping) else ""
        api_version = info.get("version", "") if isinstance(info, Mapping) else ""

        sha = sha256_hex(canonical_json_bytes(document))
        snapshot = SpecSnapshot(
            sha256=sha,
            openapi_version=version,
            title=title or "<untitled>",
            api_version=api_version or "<unversioned>",
            operations=tuple(operation_models),
            source_name=str(path),
        )
        report = _report(
            status="VALID",
            spec_path=str(path),
            sha256=sha,
            openapi_version=version,
            title=title or "<untitled>",
            api_version=api_version or "<unversioned>",
            operations=operations_detail,
            errors=(),
            coverage_gaps=tuple(gaps),
            unsupported_constructs=tuple(unsupported),
        )
        return _Analysis("VALID", document, snapshot, (), report)


def _report(
    *,
    status: str,
    spec_path: str,
    sha256: str,
    openapi_version: str,
    title: str,
    api_version: str,
    operations: tuple[OperationDetail, ...],
    errors: tuple[str, ...],
    coverage_gaps: tuple[str, ...],
    unsupported_constructs: tuple[str, ...],
) -> InspectionReport:
    return InspectionReport(
        status=status,
        spec_path=spec_path,
        sha256=sha256,
        openapi_version=openapi_version,
        title=title,
        api_version=api_version,
        operation_count=len(operations),
        operations=operations,
        errors=errors,
        coverage_gaps=coverage_gaps,
        unsupported_constructs=unsupported_constructs,
    )


def resolve_operation(
    document: Mapping[str, Any], operation_id: str
) -> tuple[str, str, dict[str, Any]] | None:
    """Resolve an operation by ID.

    Returns ``(method, path_template, operation)`` or ``None`` when not found.
    """
    paths = document.get("paths")
    if not isinstance(paths, dict):
        return None
    methods = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method in methods:
            operation = path_item.get(method)
            if isinstance(operation, dict) and operation.get("operationId") == operation_id:
                return method.upper(), str(path), operation
    return None


def _external_refs(obj: Any, found: set[str] | None = None) -> set[str]:
    if found is None:
        found = set()
    if isinstance(obj, dict):
        ref = obj.get("$ref")
        if isinstance(ref, str) and not ref.startswith("#"):
            found.add(ref)
        for value in obj.values():
            _external_refs(value, found)
    elif isinstance(obj, list):
        for value in obj:
            _external_refs(value, found)
    return found


def _has_examples(obj: Any) -> bool:
    if isinstance(obj, dict):
        if "example" in obj or "examples" in obj:
            return True
        return any(_has_examples(value) for value in obj.values())
    if isinstance(obj, list):
        return any(_has_examples(value) for value in obj)
    return False


def _contains_composition(obj: Any) -> bool:
    if isinstance(obj, dict):
        if any(key in obj for key in _COMPOSITION_KEYWORDS):
            return True
        return any(_contains_composition(value) for value in obj.values())
    if isinstance(obj, list):
        return any(_contains_composition(value) for value in obj)
    return False


def _build_operations(
    document: Mapping[str, Any],
) -> tuple[
    tuple[OperationDetail, ...],
    tuple[Operation, ...],
    list[str],
    list[str],
]:
    operations_detail: list[OperationDetail] = []
    operation_models: list[Operation] = []
    gaps: list[str] = []
    unsupported: list[str] = []

    paths = document.get("paths")
    if not isinstance(paths, dict):
        return (), (), ["paths is missing or not an object"], unsupported

    methods = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method in methods:
            operation = path_item.get(method)
            if not isinstance(operation, dict):
                continue

            operation_id = operation.get("operationId")
            if not isinstance(operation_id, str) or not operation_id.strip():
                operation_id = None
                gaps.append(f"Operation {method.upper()} {path} has no operationId")

            responses = operation.get("responses")
            response_codes: tuple[str, ...] = ()
            if isinstance(responses, dict):
                response_codes = tuple(sorted(str(code) for code in responses))

            has_request_body = "requestBody" in operation
            required_inputs: list[str] = []
            parameters = operation.get("parameters")
            if isinstance(parameters, list):
                for parameter in parameters:
                    if isinstance(parameter, dict) and parameter.get("required") is True:
                        name = parameter.get("name")
                        if isinstance(name, str):
                            required_inputs.append(f"parameter:{name}")
            request_body = operation.get("requestBody")
            if isinstance(request_body, dict) and request_body.get("required") is True:
                required_inputs.append("requestBody")

            examples_available = _has_examples(operation)

            operations_detail.append(
                OperationDetail(
                    operation_id=operation_id,
                    method=method.upper(),
                    path=str(path),
                    response_codes=response_codes,
                    has_request_body=has_request_body,
                    required_inputs=tuple(required_inputs),
                    examples_available=examples_available,
                )
            )
            operation_models.append(
                Operation(
                    method=method.upper(),
                    path=str(path),
                    operation_id=operation_id,
                    has_request_body=has_request_body,
                    response_codes=response_codes,
                )
            )

            if required_inputs and not examples_available:
                gaps.append(
                    f"Operation {operation_id or method.upper() + ' ' + str(path)} "
                    "has required inputs but no examples"
                )

    if _contains_composition(document):
        unsupported.append(
            "Schema composition keywords (oneOf/anyOf/allOf/not/if/then/else) "
            "are present; advanced semantics are not yet classified"
        )

    callbacks = document.get("callbacks")
    webhooks = document.get("webhooks")
    if isinstance(callbacks, dict) and callbacks:
        unsupported.append("Callbacks are declared but not tested")
    if isinstance(webhooks, dict) and webhooks:
        unsupported.append("Webhooks are declared but not tested")

    return tuple(operations_detail), tuple(operation_models), gaps, unsupported
