"""JSON schemas exposed to Hermes for ContractGuard tools."""

from __future__ import annotations

PING = {
    "name": "contractguard_ping",
    "description": "Health check for the ContractGuard plugin.",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    },
}

INSPECT = {
    "name": "contractguard_inspect",
    "description": "Load and validate a local OpenAPI document without making network requests.",
    "parameters": {
        "type": "object",
        "properties": {
            "spec_path": {
                "type": "string",
                "description": "Path to a local JSON or YAML OpenAPI document.",
            }
        },
        "required": ["spec_path"],
        "additionalProperties": False,
    },
}

REGISTER = {
    "name": "contractguard_register",
    "description": "Register a service with an explicit base URL and OpenAPI spec.",
    "parameters": {
        "type": "object",
        "properties": {
            "service_id": {"type": "string"},
            "spec_path": {"type": "string"},
            "base_url": {"type": "string"},
            "environment": {"type": "string"},
        },
        "required": ["service_id", "spec_path", "base_url"],
        "additionalProperties": False,
    },
}

VALIDATE_REQUEST = {
    "name": "contractguard_validate_request",
    "description": "Validate a proposed request against an OpenAPI operation without sending it.",
    "parameters": {
        "type": "object",
        "properties": {
            "service_id": {"type": "string"},
            "operation_id": {"type": "string"},
            "path_params": {"type": "object"},
            "query_params": {"type": "object"},
            "headers": {"type": "object"},
            "content_type": {"type": "string"},
            "body": {},
        },
        "required": ["service_id", "operation_id"],
        "additionalProperties": False,
    },
}

TEST = {
    "name": "contractguard_test",
    "description": "Execute a bounded live GET/HEAD request and validate the actual response.",
    "parameters": {
        "type": "object",
        "properties": {
            "service_id": {"type": "string"},
            "operation_id": {"type": "string"},
            "path_params": {"type": "object"},
            "query_params": {"type": "object"},
            "max_response_bytes": {"type": "integer"},
        },
        "required": ["service_id", "operation_id"],
        "additionalProperties": False,
    },
}

DIFF = {
    "name": "contractguard_diff",
    "description": "Compare a candidate OpenAPI document with the approved baseline.",
    "parameters": {
        "type": "object",
        "properties": {
            "service_id": {"type": "string"},
            "candidate_spec_path": {"type": "string"},
        },
        "required": ["service_id", "candidate_spec_path"],
        "additionalProperties": False,
    },
}

PROMOTE = {
    "name": "contractguard_promote_baseline",
    "description": "Promote an exact candidate spec hash to the approved baseline.",
    "parameters": {
        "type": "object",
        "properties": {
            "service_id": {"type": "string"},
            "candidate_spec_path": {"type": "string"},
            "candidate_sha256": {"type": "string"},
            "version_label": {"type": "string"},
            "reason": {"type": "string"},
        },
        "required": ["service_id", "candidate_spec_path", "candidate_sha256", "version_label"],
        "additionalProperties": False,
    },
}
