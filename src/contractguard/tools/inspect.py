"""Handler for the ``contractguard_inspect`` tool."""

from __future__ import annotations

import json
import logging
from typing import Any

from ..adapters.spec_loader import SpecLoader
from ..config import Settings
from ..domain.errors import ContractGuardError
from ..services.inspect import inspect_spec

logger = logging.getLogger(__name__)


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
        settings = Settings.from_env()
        loader = SpecLoader(max_spec_bytes=settings.max_spec_bytes)
        report = inspect_spec(loader, spec_path)
        return json.dumps(report.to_dict(), separators=(",", ":"))
    except ContractGuardError as exc:
        return json.dumps(exc.as_dict(), separators=(",", ":"))
    except Exception as exc:  # pragma: no cover - defensive boundary
        logger.exception("Unexpected error while inspecting %s", spec_path)
        return json.dumps(
            {"code": "CONTRACTGUARD_ERROR", "message": str(exc)},
            separators=(",", ":"),
        )
