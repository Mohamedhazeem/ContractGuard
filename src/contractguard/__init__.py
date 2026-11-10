"""ContractGuard implementation package."""

from __future__ import annotations

__version__ = "0.1.0"

from typing import Any

from .hooks.pre_tool_call import require_promotion_approval
from .hooks.pre_verify import pre_verify_nudge
from .tools.diff import diff_contract_tool as _diff_handler
from .tools.inspect import inspect as _inspect_handler
from .tools.ping import ping as _ping_handler
from .tools.promote import promote_baseline as _promote_handler
from .tools.register import register as _register_handler
from .tools.schemas import DIFF, INSPECT, PING, PROMOTE, REGISTER, TEST, VALIDATE_REQUEST
from .tools.test_api import test_api as _test_handler
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
        name="contractguard_test",
        toolset="contractguard",
        schema=TEST,
        handler=_test_handler,
    )
    ctx.register_tool(
        name="contractguard_diff",
        toolset="contractguard",
        schema=DIFF,
        handler=_diff_handler,
    )
    ctx.register_tool(
        name="contractguard_promote_baseline",
        toolset="contractguard",
        schema=PROMOTE,
        handler=_promote_handler,
    )
    ctx.register_hook("pre_tool_call", require_promotion_approval)
    ctx.register_hook("pre_verify", pre_verify_nudge)
    _ = ctx
