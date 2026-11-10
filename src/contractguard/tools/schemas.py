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
