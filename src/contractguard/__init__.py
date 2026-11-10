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


def register(ctx: Any) -> None:
    """Register ContractGuard tools and hooks with Hermes.

    Stage 0 scaffold: no tools or hooks are registered yet, so ``plugin.yaml``
    declares empty ``provides_tools`` and ``provides_hooks`` lists. When a tool
    is implemented, register it here **and** add its name to the manifest in the
    same change.

    Args:
        ctx: The Hermes ``PluginContext`` supplied by the plugin loader. Only
            documented methods such as ``ctx.register_tool`` and
            ``ctx.register_hook`` may be used.

    Returns:
        None.
    """
    # Intentionally empty during the scaffold stage. Registration must not
    # perform network, filesystem, or database work.
    _ = ctx
