"""Handler for ``contractguard_register``."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from ..adapters.clock import UtcClock
from ..adapters.repositories import SqliteBaselineRepository, SqliteServiceRepository
from ..adapters.spec_loader import SpecLoader
from ..config import Settings
from ..domain.errors import ContractGuardError
from ..services.registration import register_service
from .session_paths import resolve_user_path

logger = logging.getLogger(__name__)

Handler = Callable[..., str]


def make_register(ctx: Any) -> Handler:
    """Build the ``contractguard_register`` handler bound to the plugin context.

    Args:
        ctx: The Hermes plugin context.

    Returns:
        A handler with the ``(args, **kwargs) -> str`` signature Hermes expects.
    """

    def register(args: dict[str, Any], **kwargs: Any) -> str:
        """Register a service and store its current spec as a candidate baseline."""
        _ = kwargs
        service_id = args.get("service_id")
        spec_path = args.get("spec_path")
        base_url = args.get("base_url")
        environment = args.get("environment", "local-development")

        if not isinstance(service_id, str) or not service_id.strip():
            return _error("INCOMPLETE", "service_id must be a non-empty string")
        if not isinstance(spec_path, str) or not spec_path.strip():
            return _error("INCOMPLETE", "spec_path must be a non-empty string")
        if not isinstance(base_url, str) or not base_url.strip():
            return _error("INCOMPLETE", "base_url must be a non-empty string")
        if not isinstance(environment, str) or not environment.strip():
            return _error("INCOMPLETE", "environment must be a non-empty string")

        try:
            resolved = resolve_user_path(ctx, spec_path)
            settings = Settings.from_env()

            from ..adapters.sqlite import open_plugin_database

            connection = open_plugin_database()
            try:
                service_repository = SqliteServiceRepository(connection)
                baseline_repository = SqliteBaselineRepository(connection)
                loader = SpecLoader(max_spec_bytes=settings.max_spec_bytes)
                result = register_service(
                    loader=loader,
                    service_repository=service_repository,
                    baseline_repository=baseline_repository,
                    clock=UtcClock(),
                    service_id=service_id,
                    base_url=base_url,
                    environment=environment,
                    spec_path=str(resolved),
                )
                return json.dumps(result.to_dict(), separators=(",", ":"))
            finally:
                connection.close()
        except FileNotFoundError as exc:
            return _error("INCOMPLETE", str(exc))
        except ContractGuardError as exc:
            return json.dumps(exc.as_dict(), separators=(",", ":"))
        except Exception as exc:  # pragma: no cover
            logger.exception("Unexpected error while registering %s", service_id)
            payload = {"code": "CONTRACTGUARD_ERROR", "message": str(exc)}
            return json.dumps(payload, separators=(",", ":"))

    return register


def _error(code: str, message: str) -> str:
    return json.dumps({"code": code, "message": message}, separators=(",", ":"))
