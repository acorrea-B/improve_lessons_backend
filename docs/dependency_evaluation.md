# Dependency Evaluation

T114 — every dependency in `requirements.txt` and `requirements_test.txt`
is listed with its maintenance status, Python 3.14 compatibility, known
vulnerability posture at the time of adoption, transitive footprint,
license, and version pin. **Update this document on every dependency
change.**

Last reviewed: 2026-10-13 (see `research.md` for the verification notes).

## Runtime dependencies (`requirements.txt`)

| Dependency | Pin | Role | Maintenance | Python 3.14 | Vulnerability posture | Transitive footprint | License |
|---|---|---|---|---|---|---|---|
| `fastapi` | `==0.142.2` | Web framework / API layer | Actively maintained (Pydantic + Starlette orgs) | Supported (classifiers 3.10–3.14) | No known advisories at adoption; monitored via `uv pip list --outdated` + security review gate | starlette, pydantic, anyio, opentelemetry-api | MIT |
| `pymongo` | `>=4.18,<5.0` | MongoDB **async** driver (replaces Motor) | Officially maintained by MongoDB, Inc. | Supported (3.9+) | Motor scheduled for deprecation — avoided; pymongo advisories tracked by upstream | dnspython | Apache-2.0 |
| `pydantic[email]` | `>=2.9` | DTOs, request/response validation (`EmailStr` = RFC-5322) | Actively maintained (Pydantic org) | Supported | pydantic-core advisories monitored; no known open issues at adoption | pydantic-core, email-validator, typing-extensions | MIT |
| `httpx` | unbounded minor, locked at install time | Async HTTP client (secrets provider, emulated SES) | Actively maintained (encode org) | Supported | HTTP/2 advisories tracked (not enabled here) | httpcore, anyio, certifi | BSD-3-Clause |
| `niquests` | `>=3.21,<4` | **Synchronous** HTTP client for the AI provider adapter (Ollama native API, `POST /api/chat`) | Actively maintained (jawah/niquests) | Supported (3.8+, wheels for 3.14/3.15) | No known advisories at adoption; `urllib3-future` advisories tracked upstream | urllib3-future, charset-normalizer, wassima, qh3, jh2 | Apache-2.0 |
| `boto3` | `>=1.35,<2.0` | AWS SDK: SES `SendEmail` (v1) + Secrets Manager `GetSecretValue` (real adapter + LocalStack emulation) | Actively maintained (AWS Labs, botocore) | Supported (3.9+) | Pure Python over botocore; advisories tracked upstream | botocore, jmespath, python-dateutil, urllib3, s3transfer | Apache-2.0 |
| `langgraph` | unbounded minor | Corrective-loop state machine (research.md § 4) | Actively maintained (LangChain org) | Supported (3.10+) | Monitored; no known advisories at adoption | langchain-core, langgraph-* family, orjson, xxhash | MIT |
| `uvicorn` | unbounded minor | ASGI server (development + runtime images) | Actively maintained (encode org) | Supported | httptools/uvloop extras not installed (pure-python extras) | click, h11 | BSD-3-Clause |
| `numpy` | unbounded minor | In-process cosine similarity (local vector adapter) | Actively maintained (NumFOCUS) | Supported (3.14 wheels available) | C-coded; CVEs are rare and tracked upstream | none | BSD-3-Clause |

## Test-only dependencies (`requirements_test.txt`)

| Dependency | Pin | Role | Maintenance | Python 3.14 | Vulnerability posture | License |
|---|---|---|---|---|---|---|
| `vcrpy` | `>=8.3` | HTTP record/replay for outbound integrations | Actively maintained | Supported | No known advisories at adoption | MIT |

### Why `niquests` and not `httpx` for the AI adapter

`httpx` is the async HTTP client of the runtime, but the AI provider
adapter uses `niquests` in **synchronous** mode (wrapped in
`asyncio.to_thread`, the house pattern for synchronous clients). The
reason is test coverage, not latency: **vcrpy intercepts the standard
`urllib3`**, and niquests' synchronous mode drives the standard `urllib3`
too, while its async mode drives `urllib3-future` under an internal
alias that vcrpy does not patch.

Measured against a local HTTP server with `niquests 3.21.2` + `vcrpy
8.3.0`:

| Combination | Result |
|---|---|
| niquests **sync** + vcrpy | ✅ records and replays without network |
| niquests **async** + vcrpy | ❌ not intercepted (hits the real network) |
| **`asyncio.to_thread` + niquests sync + vcrpy** | ✅ records and replays without network — the production path |

The measured HTTP overhead is 88–123 ms against 10.7–20.8 s of
inference (0.5–1.1%), so the switch is not a latency optimization: it is
what keeps the test suite free of network access. The `langgraph` row
above and the `httpx` row both stay: `httpx` still serves the secrets
provider and the emulated SES, and `langgraph` still runs the corrective
loop.

### AI provider authentication

The Ollama provider **does not authenticate**: the adapter sends no
credentials and resolves no secret. The `improve/ai/*-api-key` secrets
seeded in LocalStack are therefore NOT used by this provider and must
not be read for it. A future provider that does authenticate reuses the
existing `SecretProvider` port.

Rejected at planning (research.md § 9): `pytest` (plan mandates stdlib
`unittest`), `pytest-freezer` (unapproved), `mongomock` (real-MongoDB
integration tests are mandatory), `pytz` (forbidden by the UTC standard;
stdlib `zoneinfo` covers it), `arrow`/`pendulum` (stdlib coverage).

Dependency-selection policy: any new dependency requires (a) an active
maintenance signal, (b) Python 3.14 support, (c) a documented role, and
(d) compliance review against the constitution's dependencies policy.