"""ContractGuard implementation package.

Layer map (dependencies point inward):

``domain/``
    Pure enums, immutable records, invariants, ports, and domain errors. Standard
    library only. No I/O, no third-party libraries, no Hermes imports.
``services/``
    Use-case orchestration. Depends on ``domain/`` and receives adapters through
    constructor injection.
``adapters/``
    Concrete I/O: SQLite repositories, HTTPX transport, OpenAPI parsing and
    validation, Hermes storage glue. Translates external data into domain types.
``tools/``
    Thin Hermes tool handlers and JSON schemas.
``hooks/``
    Hermes lifecycle hooks.

The root ``__init__.py`` of the plugin directory re-exports :func:`register` from
this module. Keep registration fast, synchronous, and free of I/O.
"""

from __future__ import annotations

from typing import Any

__version__ = "0.1.0"

__all__ = ["__version__", "register"]


from .tools.ping import ping as _ping_handler
from .tools.schemas import PING


def register(ctx: Any) -> None:
    """Register ContractGuard tools and hooks with Hermes.

    Slice 0 registers a single health-check tool so the Hermes plugin skeleton,
    manifest, and registration path can be validated end to end. No validation,
    storage, or network work happens here.
    """
    ctx.register_tool(
        name="contractguard_ping",
        toolset="contractguard",
        schema=PING,
        handler=_ping_handler,
    )
    _ = ctx
