"""JSON schemas exposed to Hermes for ContractGuard tools."""

from __future__ import annotations

PING = {
    "name": "contractguard_ping",
    "description": (
        "Health check for the ContractGuard plugin. Returns the plugin name and version."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    },
}

INSPECT = {
    "name": "contractguard_inspect",
    "description": ("Load and validate a local OpenAPI document without making network requests."),
    "parameters": {
        "type": "object",
        "properties": {
            "spec_path": {
                "type": "string",
                "description": (
                    "Absolute or relative path to a local JSON or YAML OpenAPI document."
                ),
            }
        },
        "required": ["spec_path"],
        "additionalProperties": False,
    },
}

REGISTER = {
    "name": "contractguard_register",
    "description": (
        "Register a service with an explicit base URL and OpenAPI spec. Validates "
        "the spec before storing anything. Stores the current spec as a candidate "
        "baseline; it does not approve it."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "service_id": {"type": "string", "description": "Lowercase slug for the service."},
            "spec_path": {"type": "string", "description": "Path to the OpenAPI document."},
            "base_url": {
                "type": "string",
                "description": "Explicit loopback base URL, e.g. http://127.0.0.1:8000.",
            },
            "environment": {
                "type": "string",
                "description": "Environment label. Defaults to local-development.",
            },
        },
        "required": ["service_id", "spec_path", "base_url"],
        "additionalProperties": False,
    },
}

PROMOTE = {
    "name": "contractguard_promote_baseline",
    "description": (
        "Promote an exact candidate spec hash to the approved baseline. Requires "
        "human approval through the pre_tool_call hook."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "service_id": {"type": "string"},
            "candidate_spec_path": {"type": "string"},
            "candidate_sha256": {
                "type": "string",
                "description": "Exact 64-character SHA-256 of the candidate.",
            },
            "version_label": {"type": "string"},
            "reason": {"type": "string"},
        },
        "required": ["service_id", "candidate_spec_path", "candidate_sha256", "version_label"],
        "additionalProperties": False,
    },
}
