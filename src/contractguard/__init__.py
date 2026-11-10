"""ContractGuard implementation package."""

from __future__ import annotations

__version__ = "0.1.0"

from typing import Any

from .hooks.pre_tool_call import require_promotion_approval
from .tools.inspect import inspect as _inspect_handler
from .tools.ping import ping as _ping_handler
from .tools.promote import promote_baseline as _promote_handler
from .tools.register import register as _register_handler
from .tools.schemas import INSPECT, PING, PROMOTE, REGISTER, VALIDATE_REQUEST
from .tools.validate_request import validate_request as _validate_request_handler


def register(ctx: Any) -> None:
    """Register ContractGuard tools and hooks with Hermes."""
    ctx.register_tool(
        name="contractguard_ping",
        toolset="contractguard",
        schema=PING,
        handler=_ping_handler,
    )
    ctx.register_tool(
        name="contractguard_inspect",
        toolset="contractguard",
        schema=INSPECT,
        handler=_inspect_handler,
    )
    ctx.register_tool(
        name="contractguard_register",
        toolset="contractguard",
        schema=REGISTER,
        handler=_register_handler,
    )
    ctx.register_tool(
        name="contractguard_validate_request",
        toolset="contractguard",
        schema=VALIDATE_REQUEST,
        handler=_validate_request_handler,
    )
    ctx.register_tool(
        name="contractguard_promote_baseline",
        toolset="contractguard",
        schema=PROMOTE,
        handler=_promote_handler,
    )
    ctx.register_hook("pre_tool_call", require_promotion_approval)
    _ = ctx
