"""JSON schemas exposed to Hermes for ContractGuard tools.

These dictionaries are what the model reads to decide when to call a tool and
which arguments to supply. Descriptions must state what the tool does, what it
does not do, and its safety boundary.
"""

from __future__ import annotations

PING = {
    "name": "contractguard_ping",
    "description": (
        "Health check for the ContractGuard plugin. Returns the plugin name and "
        "version. Use this to confirm that ContractGuard is installed, enabled, "
        "and registered with Hermes."
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
    "description": (
        "Load and validate a local OpenAPI document without making network "
        "requests. Returns the OpenAPI version, API title and version, operation "
        "inventory, declared response codes, request-body presence, required "
        "inputs, example availability, validation errors, coverage gaps, and a "
        "SHA-256 of the normalized document."
    ),
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
