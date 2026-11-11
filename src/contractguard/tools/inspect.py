"""Handler for the ``contractguard_inspect`` tool."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from ..adapters.spec_loader import SpecLoader
from ..config import Settings
from ..domain.errors import ContractGuardError
from ..services.inspect import inspect_spec
from .session_paths import resolve_user_path

logger = logging.getLogger(__name__)

Handler = Callable[..., str]


def make_inspect(ctx: Any) -> Handler:
    """Build the ``contractguard_inspect`` handler bound to the plugin context.

    The context is used to resolve a relative ``spec_path`` against the
    calling session's working directory.

    Args:
        ctx: The Hermes plugin context.

    Returns:
        A handler with the ``(args, **kwargs) -> str`` signature Hermes expects.
    """

    def inspect(args: dict[str, Any], **kwargs: Any) -> str:
        """Inspect and validate one local OpenAPI document.

        Args:
            args: Tool arguments. Must contain ``spec_path``.
            **kwargs: Hermes-provided context.

        Returns:
            A JSON string describing the document, its operations, and any
            validation or coverage findings.
        """
        _ = kwargs
        spec_path = args.get("spec_path")
        if not isinstance(spec_path, str) or not spec_path.strip():
            return json.dumps(
                {"code": "INCOMPLETE", "message": "spec_path must be a non-empty string"},
                separators=(",", ":"),
            )

        try:
            resolved = resolve_user_path(ctx, spec_path)
            settings = Settings.from_env()
            loader = SpecLoader(max_spec_bytes=settings.max_spec_bytes)
            report = inspect_spec(loader, str(resolved))
            return json.dumps(report.to_dict(), separators=(",", ":"))
        except FileNotFoundError as exc:
            return json.dumps({"code": "INCOMPLETE", "message": str(exc)}, separators=(",", ":"))
        except ContractGuardError as exc:
            return json.dumps(exc.as_dict(), separators=(",", ":"))
        except Exception as exc:  # pragma: no cover - defensive boundary
            logger.exception("Unexpected error while inspecting %s", spec_path)
            return json.dumps(
                {"code": "CONTRACTGUARD_ERROR", "message": str(exc)},
                separators=(",", ":"),
            )

    return inspect
