"""Clock adapter providing timezone-aware UTC timestamps."""

from __future__ import annotations

from datetime import datetime, timezone


class UtcClock:
    """Clock implementation for the :class:`~contractguard.domain.ports.Clock` port."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)
