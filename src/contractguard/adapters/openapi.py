"""OpenAPI-core request and response adapters.

This is the Slice 0 GO/NO-GO spike surface. It is the only module allowed to
import ``openapi_core``. Everything above this layer depends on the protocol
objects and the helper functions defined here, never on ``openapi_core``
directly.

The adapter disables schema casting. OpenAPI-core casts values (for example a
JSON string ``"49.99"`` to the number ``49.99``) before validating them, which
would hide the exact type mismatch ContractGuard exists to report. Disabling
casting keeps the validator honest: a string is a string.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from openapi_core import OpenAPI


class _NoOpCaster:
    """Caster that performs no conversion, preserving the original JSON type."""

    def cast(self, value: Any) -> Any:
        return value


class _NoOpCastersFactory:
    """Factory returning :class:`_NoOpCaster` for every schema."""

    def create(
        self,
        schema: Any,
        format_validators: Any = None,
        extra_format_validators: Any = None,
    ) -> _NoOpCaster:
        _ = schema, format_validators, extra_format_validators
        return _NoOpCaster()


def make_openapi(spec: Mapping[str, Any]) -> OpenAPI:
    """Build an ``OpenAPI`` instance with casting disabled.

    Args:
        spec: Parsed OpenAPI document as a mapping.

    Returns:
        A configured ``OpenAPI`` application.

    Raises:
        ValueError: If the document is not a supported OpenAPI specification.
    """
    from openapi_core import Config, OpenAPI

    return OpenAPI.from_dict(
        cast(Any, spec),
        config=Config(schema_casters_factory=cast(Any, _NoOpCastersFactory())),
    )


class OpenApiRequestAdapter:
    """Adapter satisfying ``openapi_core.protocols.Request``."""

    def __init__(
        self,
        *,
        method: str,
        host_url: str,
        path: str,
        full_url_pattern: str,
        parameters: Any = None,
        body: bytes | None = None,
        content_type: str = "",
    ) -> None:
        if not method:
            raise ValueError("method must be non-empty")
        if not host_url:
            raise ValueError("host_url must be non-empty")
        if not path.startswith("/"):
            raise ValueError("path must start with '/'")
        if not full_url_pattern:
            raise ValueError("full_url_pattern must be non-empty")

        self._method = method.lower()
        self._host_url = host_url
        self._path = path
        self._full_url_pattern = full_url_pattern
        if parameters is None:
            try:
                from openapi_core.datatypes import RequestParameters
            except ImportError as exc:
                raise RuntimeError("openapi_core is required") from exc
            self.parameters = RequestParameters()
        else:
            self.parameters = parameters
        self._body = body
        self._content_type = content_type.lower()

    @property
    def method(self) -> str:
        return self._method

    @property
    def host_url(self) -> str:
        return self._host_url

    @property
    def path(self) -> str:
        return self._path

    @property
    def full_url_pattern(self) -> str:
        return self._full_url_pattern

    @property
    def body(self) -> bytes | None:
        return self._body

    @property
    def content_type(self) -> str:
        return self._content_type


class OpenApiResponseAdapter:
    """Adapter satisfying ``openapi_core.protocols.Response``."""

    def __init__(
        self,
        *,
        status_code: int,
        headers: Mapping[str, Any],
        content_type: str,
        data: bytes | None,
    ) -> None:
        if not 100 <= status_code <= 599:
            raise ValueError("status_code must be a valid HTTP status")
        if not content_type:
            raise ValueError("content_type must be non-empty")

        self._status_code = status_code
        self._headers = dict(headers)
        self._content_type = content_type.lower()
        self._data = data

    @property
    def status_code(self) -> int:
        return self._status_code

    @property
    def headers(self) -> Mapping[str, Any]:
        return self._headers

    @property
    def content_type(self) -> str:
        return self._content_type

    @property
    def data(self) -> bytes | None:
        return self._data


def validate_request(openapi: OpenAPI, request: OpenApiRequestAdapter) -> list[Exception]:
    """Collect every request validation error without raising.

    Args:
        openapi: Configured OpenAPI application.
        request: Adapter instance.

    Returns:
        All errors yielded by ``openapi.request_validator.iter_errors``.
    """
    return list(openapi.request_validator.iter_errors(request))


def validate_response(
    openapi: OpenAPI, request: OpenApiRequestAdapter, response: OpenApiResponseAdapter
) -> list[Exception]:
    """Collect every response validation error without raising.

    Args:
        openapi: Configured OpenAPI application.
        request: Adapter associated with the response.
        response: Adapter wrapping the captured response.

    Returns:
        All errors yielded by ``openapi.response_validator.iter_errors``.
    """
    return list(openapi.response_validator.iter_errors(request, response))


def from_httpx_response(
    response: Any, *, content_type: str | None = None
) -> OpenApiResponseAdapter:
    """Build a response adapter from an ``httpx.Response``.

    The response body must already have been read (``response.content``).

    Args:
        response: An ``httpx.Response`` instance.
        content_type: Override for the response content type. When omitted, the
            ``content-type`` header is used.

    Returns:
        A populated :class:`OpenApiResponseAdapter`.

    Raises:
        RuntimeError: If ``httpx`` is not installed.
    """
    try:
        import httpx  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("httpx is required to adapt an httpx.Response") from exc

    resolved_type = content_type or response.headers.get("content-type", "")
    if not resolved_type:
        raise ValueError("response has no content-type header or override")

    return OpenApiResponseAdapter(
        status_code=response.status_code,
        headers=dict(response.headers),
        content_type=resolved_type,
        data=response.content,
    )
