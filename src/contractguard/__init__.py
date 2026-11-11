"""ContractGuard implementation package."""

from __future__ import annotations

from typing import Any

__version__ = "0.2.0"

from .hooks.pre_tool_call import require_promotion_approval
from .hooks.pre_verify import pre_verify_nudge
from .tools.diff import make_diff
from .tools.history import history
from .tools.inspect import make_inspect
from .tools.ping import ping
from .tools.promote import make_promote
from .tools.register import make_register
from .tools.schemas import DIFF, HISTORY, INSPECT, PING, PROMOTE, REGISTER, TEST, VALIDATE_REQUEST
from .tools.test_api import test_api
from .tools.validate_request import validate_request

__all__ = ["__version__", "register"]


def register(ctx: Any) -> None:
    """Register ContractGuard tools and hooks with Hermes."""
    ctx.register_tool(
        name="contractguard_ping",
        toolset="contractguard",
        schema=PING,
        handler=ping,
    )
    ctx.register_tool(
        name="contractguard_inspect",
        toolset="contractguard",
        schema=INSPECT,
        handler=make_inspect(ctx),
    )
    ctx.register_tool(
        name="contractguard_register",
        toolset="contractguard",
        schema=REGISTER,
        handler=make_register(ctx),
    )
    ctx.register_tool(
        name="contractguard_validate_request",
        toolset="contractguard",
        schema=VALIDATE_REQUEST,
        handler=validate_request,
    )
    ctx.register_tool(
        name="contractguard_test",
        toolset="contractguard",
        schema=TEST,
        handler=test_api,
    )
    ctx.register_tool(
        name="contractguard_diff",
        toolset="contractguard",
        schema=DIFF,
        handler=make_diff(ctx),
    )
    ctx.register_tool(
        name="contractguard_history",
        toolset="contractguard",
        schema=HISTORY,
        handler=history,
    )
    ctx.register_tool(
        name="contractguard_promote_baseline",
        toolset="contractguard",
        schema=PROMOTE,
        handler=make_promote(ctx),
    )
    ctx.register_hook("pre_tool_call", require_promotion_approval)
    ctx.register_hook("pre_verify", pre_verify_nudge)
    _ = ctx
