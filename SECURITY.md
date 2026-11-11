# Security Policy

## Scope

ContractGuard reads local OpenAPI documents and can send HTTP requests to a
**loopback** development target. It stores an immutable copy of every approved
contract baseline, plus redacted evidence receipts, in the Hermes-managed plugin
database.

## Security model

| Area | Policy |
|---|---|
| Live targets | Loopback only — `localhost`, `127.0.0.1`, `::1`. Remote hosts are refused. |
| Live methods | `GET` and `HEAD` only. Write methods are preflight-only and never dispatched. |
| Redirects | Never followed. A `3xx` response is reported as-is. |
| TLS | Certificate verification is always enabled. No `verify=False` path exists. |
| Proxy env | `trust_env=False`; environment proxy settings are ignored. |
| Timeouts | Explicit per-request budget (default 5 s, hard cap 30 s). |
| Response size | Streaming read with a hard cap (default 1 MiB); the read stops at the cap. |
| Retries / concurrency | Disabled. One request per tool call. |
| Credentials | `Authorization`, `Cookie`, `Proxy-Authorization`, and API-key headers are rejected from tool arguments. |
| Evidence | Full request/response bodies are not persisted. Only type names, JSON Pointers, status codes, sizes, and durations are stored. |
| Storage | Hermes plugin storage (`plugin_db` / `plugin_data_dir`) only. Never the plugin install directory. |
| Baselines | Immutable, content-addressed (SHA-256). Promotion requires human approval and exact hash match. |
| External `$ref` | Blocked. ContractGuard never fetches a remote schema. |
| Telemetry | None. No usage reporting, no analytics, no outbound calls to any third party. |

## Out of scope (documented MVP limits)

- Remote HTTPS targets. Support requires a reviewed allowlist, DNS/IP pinning,
  and DNS-rebinding protection. Not implemented.
- Live `POST`/`PUT`/`PATCH`/`DELETE`. Not implemented.
- OAuth or API-key authentication. Not implemented.
- Multi-step / stateful API workflows. Not implemented.
- Non-JSON media types. Not implemented.

## Reporting a vulnerability

Open a private security advisory on the repository, or contact the maintainer
directly. Please include the affected version, the OpenAPI document used, the
exact tool call, and the observed behaviour. Do not include production traffic
or real credentials in the report.

Please do not test against systems you do not own or operate.

## Supported versions

| Version | Supported |
|---|---|
| 0.2.x | Yes |
| < 0.2 | No — upgrade before reporting |
