"""Optional ``pre_verify`` hook for ContractGuard."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

_API_PATH_SUFFIXES = frozenset(
    {".py", ".yaml", ".yml", ".json", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs"}
)


def pre_verify_nudge(
    *,
    coding: bool = False,
    attempt: int = 0,
    changed_paths: Iterable[str] | None = None,
    **kwargs: Any,
) -> dict[str, str] | None:
    """Return a one-shot nudge asking Hermes to run ContractGuard checks.

    The hook never performs I/O. It only inspects the supplied context and
    returns a continue directive when all of the following hold:

    - ``coding`` is true;
    - ``attempt`` is zero (one nudge per turn);
    - at least one changed path looks like an API or contract file.
    """
    _ = kwargs
    if not coding:
        return None
    if attempt != 0:
        return None

    paths = list(changed_paths or [])
    if not any(_looks_like_api_path(path) for path in paths):
        return None

    return {
        "action": "continue",
        "message": (
            "ContractGuard: API or contract files changed. Before finishing, "
            "run contractguard_diff and/or contractguard_test to verify the "
            "contract and live response."
        ),
    }


def _looks_like_api_path(path: str) -> bool:
    if not isinstance(path, str) or not path.strip():
        return False
    lowered = path.lower()
    if lowered.endswith(tuple(_API_PATH_SUFFIXES)):
        return True
    return any(token in lowered for token in ("openapi", "swagger", "contract"))


__all__ = ["pre_verify_nudge"]
