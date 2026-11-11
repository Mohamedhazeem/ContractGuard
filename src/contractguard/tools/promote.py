"""Handler for ``contractguard_promote_baseline``."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from ..adapters.clock import UtcClock
from ..adapters.repositories import (
    SqliteBaselineRepository,
    SqliteServiceRepository,
    new_baseline_id,
)
from ..adapters.spec_loader import SpecLoader
from ..config import Settings
from ..domain.errors import ContractGuardError, NotFoundError
from ..domain.models import Baseline
from .session_paths import resolve_user_path

logger = logging.getLogger(__name__)

Handler = Callable[..., str]


def make_promote(ctx: Any) -> Handler:
    """Build the ``contractguard_promote_baseline`` handler.

    Args:
        ctx: The Hermes plugin context.

    Returns:
        A handler with the ``(args, **kwargs) -> str`` signature Hermes expects.
    """

    def promote_baseline(args: dict[str, Any], **kwargs: Any) -> str:
        """Promote a candidate spec to the approved baseline after approval."""
        _ = kwargs
        service_id = args.get("service_id")
        candidate_spec_path = args.get("candidate_spec_path")
        candidate_sha256 = args.get("candidate_sha256")
        version_label = args.get("version_label")
        reason = args.get("reason")

        if not isinstance(service_id, str) or not service_id.strip():
            return _error("INCOMPLETE", "service_id must be a non-empty string")
        if not isinstance(candidate_spec_path, str) or not candidate_spec_path.strip():
            return _error("INCOMPLETE", "candidate_spec_path must be a non-empty string")
        if not isinstance(candidate_sha256, str) or len(candidate_sha256) != 64:
            return _error(
                "INCOMPLETE", "candidate_sha256 must be a 64-character SHA-256 hex digest"
            )
        if not isinstance(version_label, str) or not version_label.strip():
            return _error("INCOMPLETE", "version_label must be a non-empty string")

        try:
            resolved = resolve_user_path(ctx, candidate_spec_path)
            settings = Settings.from_env()

            from ..adapters.sqlite import open_plugin_database

            connection = open_plugin_database()
            try:
                service_repository = SqliteServiceRepository(connection)
                baseline_repository = SqliteBaselineRepository(connection)
                service = service_repository.get(service_id)
                if service is None:
                    raise NotFoundError(f"Service {service_id!r} is not registered.")

                loader = SpecLoader(max_spec_bytes=settings.max_spec_bytes)
                loaded = loader.load_file(resolved)
                if loaded.snapshot.sha256 != candidate_sha256:
                    return _error(
                        "INCOMPLETE",
                        "Candidate hash mismatch: the file changed since it was reviewed. "
                        f"Expected {candidate_sha256}, got {loaded.snapshot.sha256}.",
                    )

                now = UtcClock().now()
                current = baseline_repository.current(service_id)
                baseline = Baseline(
                    baseline_id=new_baseline_id(),
                    service_id=service_id,
                    spec_sha256=loaded.snapshot.sha256,
                    spec_json=json.dumps(
                        loaded.document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                    ),
                    promoted_at=now,
                    version_label=version_label,
                    parent_baseline_id=current.baseline_id if current is not None else None,
                    is_current=True,
                )
                persisted = baseline_repository.promote(
                    baseline,
                    expected_current_id=current.baseline_id if current is not None else None,
                )
                result = {
                    "service_id": service_id,
                    "baseline_id": persisted.baseline_id,
                    "version_label": persisted.version_label,
                    "spec_sha256": persisted.spec_sha256,
                    "promoted_at": persisted.promoted_at.isoformat(),
                    "parent_baseline_id": persisted.parent_baseline_id,
                    "reason": reason,
                }
                return json.dumps(result, separators=(",", ":"))
            finally:
                connection.close()
        except FileNotFoundError as exc:
            return _error("INCOMPLETE", str(exc))
        except ContractGuardError as exc:
            return json.dumps(exc.as_dict(), separators=(",", ":"))
        except Exception as exc:  # pragma: no cover
            logger.exception("Unexpected error while promoting baseline for %s", service_id)
            payload = {"code": "CONTRACTGUARD_ERROR", "message": str(exc)}
            return json.dumps(payload, separators=(",", ":"))

    return promote_baseline


def _error(code: str, message: str) -> str:
    return json.dumps({"code": code, "message": message}, separators=(",", ":"))
