"""Handler for the ``contractguard_ping`` tool."""

from __future__ import annotations

import json
from typing import Any

from ..version import __version__


def ping(args: dict[str, Any], **kwargs: Any) -> str:
    """Return a small JSON health-check payload.

    Args:
        args: Tool arguments. Ignored; the tool takes no inputs.
        **kwargs: Hermes-provided context. Ignored.

    Returns:
        A JSON string with ``pong``, ``plugin``, and ``version`` fields.
    """
    _ = args, kwargs
    return json.dumps(
        {"pong": True, "plugin": "contractguard", "version": __version__},
        separators=(",", ":"),
    )
