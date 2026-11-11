"""Resolution of user-supplied paths against the calling session's directory.

A plugin's handlers run inside the Hermes process, whose working directory is
the gateway's — not the directory the user launched Hermes from. A relative path
such as ``demo/openapi.yaml`` must therefore be resolved against the session's
recorded working directory, which Hermes exposes through
``ctx.session_cwd()``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def session_base_dir(ctx: Any) -> Path:
    """Return the calling session's working directory.

    Falls back to the process working directory when the session has no recorded
    directory (for example a tool call made outside any session).
    """
    try:
        recorded = ctx.session_cwd()
    except Exception:
        recorded = ""
    if recorded:
        candidate = Path(recorded)
        if candidate.is_dir():
            return candidate
    return Path.cwd()


def resolve_user_path(ctx: Any, raw: str) -> Path:
    """Resolve a user-supplied path against the session's working directory.

    Args:
        ctx: The Hermes plugin context.
        raw: The path exactly as the user (or the model) supplied it.

    Returns:
        An absolute path.

    Raises:
        FileNotFoundError: If the path does not exist under the session
            directory or the process directory.
    """
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        if candidate.exists():
            return candidate.resolve()
        raise FileNotFoundError(f"No such file: {candidate}")

    base = session_base_dir(ctx)
    resolved = (base / candidate).resolve()
    if resolved.exists():
        return resolved

    # Fall back to the process directory so a path that only resolves there
    # still works (for example a spec outside the session's project).
    process_resolved = candidate.resolve()
    if process_resolved.exists():
        return process_resolved

    raise FileNotFoundError(f"No such file: {candidate} (looked in {base} and {Path.cwd()})")
