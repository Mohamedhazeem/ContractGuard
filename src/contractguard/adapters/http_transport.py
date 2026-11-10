"""Bounded HTTP transport for live GET/HEAD verification."""

from __future__ import annotations

import time
from urllib.parse import urlsplit

import httpx

from ..config import FOLLOW_REDIRECTS, TRUST_ENV, VERIFY_TLS
from ..domain.errors import IncompleteInputError, PolicyError
from ..domain.models import HttpRequest, HttpResponse

_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_ALLOWED_METHODS = frozenset({"GET", "HEAD"})


class HttpxTransport:
    """HTTPX transport enforcing ContractGuard's safety policy."""

    def __init__(
        self,
        *,
        max_response_bytes: int,
        allowed_methods: frozenset[str] | None = None,
    ) -> None:
        if max_response_bytes < 1:
            raise ValueError("max_response_bytes must be positive")
        self._max_response_bytes = max_response_bytes
        self._allowed_methods = allowed_methods if allowed_methods is not None else _ALLOWED_METHODS

    def send(self, request: HttpRequest, *, timeout_seconds: float) -> HttpResponse:
        method = request.method.upper()
        if method not in self._allowed_methods:
            raise PolicyError(f"Live method is not allowed: {method}")

        try:
            parts = urlsplit(request.url)
        except ValueError as exc:
            raise PolicyError(f"Invalid target URL: {exc}") from exc

        if parts.scheme not in {"http", "https"}:
            raise PolicyError("Target URL must use http or https.")
        if parts.username is not None or parts.password is not None:
            raise PolicyError("Target URL must not contain credentials.")
        if parts.hostname is None or parts.hostname.lower() not in _LOOPBACK_HOSTS:
            raise PolicyError("Live targets must be loopback addresses in the MVP.")

        started = time.monotonic()
        try:
            with (
                httpx.Client(
                    follow_redirects=FOLLOW_REDIRECTS,
                    verify=VERIFY_TLS,
                    trust_env=TRUST_ENV,
                    timeout=httpx.Timeout(timeout_seconds),
                ) as client,
                client.stream(
                    method,
                    request.url,
                    headers=dict(request.headers),
                    content=request.body,
                    timeout=httpx.Timeout(timeout_seconds),
                ) as response,
            ):
                if 300 <= response.status_code < 400:
                    location = response.headers.get("location", "")
                    raise IncompleteInputError(
                        f"Redirect not followed (HTTP {response.status_code}); Location: {location}"
                    )

                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    if total + len(chunk) > self._max_response_bytes:
                        raise IncompleteInputError(
                            f"Response exceeded the {self._max_response_bytes}-byte limit."
                        )
                    chunks.append(chunk)
                    total += len(chunk)

                body = b"".join(chunks)
                elapsed_ms = int((time.monotonic() - started) * 1000)
                return HttpResponse(
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    body=body,
                    elapsed_ms=elapsed_ms,
                )
        except (IncompleteInputError, PolicyError):
            raise
        except httpx.TimeoutException as exc:
            raise IncompleteInputError(f"Request timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise IncompleteInputError(f"Transport error: {exc}") from exc
