"""Hermes entry point for ContractGuard.

Hermes imports a native directory plugin as ``hermes_plugins.<slug>`` and requires
exactly one public integration point in this file: ``register(ctx)``.

This module is deliberately a thin bootstrap. It puts the ``src/`` directory on
``sys.path`` so the implementation can use a standard src layout, then re-exports
``register`` from the ``contractguard`` package. No validation, networking, or
storage work happens at import or registration time.

Only documented ``ctx.*`` APIs may be used by the plugin. Do not patch, wrap, or
monkeypatch Hermes core modules here.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from contractguard import register as register  # noqa: E402

__all__ = ["register"]
