"""Hermes lifecycle hooks for ContractGuard."""

from __future__ import annotations

from typing import Any


def require_promotion_approval(
    tool_name: str = "",
    args: Any = None,
    task_id: str = "",
    **kwargs: Any,
) -> dict[str, str] | None:
    """Escalate baseline promotion to Hermes' human-approval gate.

    Args:
        tool_name: Name of the tool being invoked.
        args: Tool arguments.
        task_id: Hermes task identifier.
        **kwargs: Additional Hermes payload fields.

    Returns:
        An approval directive for promotion, otherwise ``None``.
    """
    _ = task_id, kwargs
    if tool_name != "contractguard_promote_baseline":
        return None

    payload = args if isinstance(args, dict) else {}
    service_id = payload.get("service_id", "unknown")
    candidate_hash = payload.get("candidate_sha256", "unknown")
    return {
        "action": "approve",
        "message": (
            f"Approve ContractGuard baseline promotion for {service_id} "
            f"to candidate SHA-256 {candidate_hash}?"
        ),
    }
