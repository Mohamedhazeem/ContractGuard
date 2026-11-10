"""Inspection use case for OpenAPI documents."""

from __future__ import annotations

from pathlib import Path

from ..domain.models import InspectionReport
from ..domain.ports import SpecLoader


def inspect_spec(loader: SpecLoader, spec_path: str | Path) -> InspectionReport:
    """Inspect one OpenAPI document through the supplied loader.

    Args:
        loader: Spec loader adapter.
        spec_path: Path to the JSON or YAML document.

    Returns:
        The inspection report, including ``VALID``, ``INVALID_SPEC``, or
        ``UNSUPPORTED`` status.
    """
    return loader.inspect(Path(spec_path))
