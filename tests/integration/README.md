# Integration tests

Integration tests exercise adapters against real dependencies, but never against
untrusted or remote systems.

Planned coverage:

- `openapi-core` request and response adapters (the Slice 0 GO/NO-GO gate).
- Bounded HTTPX transport against a loopback ASGI app or a socket bound to
  `127.0.0.1` on an ephemeral port.
- SQLite repositories, including transactional baseline promotion and stale
  compare-and-swap rejection.
- Redaction checks across evidence persistence and tool output.

Rules:

- Mark tests with `@pytest.mark.integration`.
- Add `@pytest.mark.network` only when a listening socket is required.
- Bind to loopback and allocate port `0`; never use a fixed port.
- Never hit the internet, a real production API, or a non-loopback address.
- Keep the canonical OpenAPI document in `tests/fixtures/openapi/giftshop.yaml`
  rather than duplicating it here.
