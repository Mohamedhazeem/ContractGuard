"""Tests for ContractGuard hooks."""

from __future__ import annotations

from contractguard.hooks.pre_tool_call import require_promotion_approval
from contractguard.hooks.pre_verify import pre_verify_nudge


def test_pre_tool_call_only_gates_promotion() -> None:
    assert (
        require_promotion_approval(tool_name="contractguard_inspect", args={}, task_id="t") is None
    )
    directive = require_promotion_approval(
        tool_name="contractguard_promote_baseline",
        args={"service_id": "svc", "candidate_sha256": "abc"},
        task_id="t",
    )
    assert directive is not None
    assert directive["action"] == "approve"


def test_pre_verify_nudges_once_for_api_paths() -> None:
    directive = pre_verify_nudge(
        coding=True,
        attempt=0,
        changed_paths=["src/api/products.py", "docs/readme.md"],
    )
    assert directive is not None
    assert directive["action"] == "continue"

    assert pre_verify_nudge(coding=True, attempt=1, changed_paths=["src/api/products.py"]) is None
    assert pre_verify_nudge(coding=False, attempt=0, changed_paths=["src/api/products.py"]) is None
    assert pre_verify_nudge(coding=True, attempt=0, changed_paths=["README.md"]) is None
