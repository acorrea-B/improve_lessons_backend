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
| `langgraph` | unbounded minor | Corrective-loop state machine (research.md § 4) | Actively maintained (LangChain org) | Supported (3.10+) | Monitored; no known advisories at adoption | langchain-core, langgraph-* family, orjson, xxhash | MIT |
| `uvicorn` | unbounded minor | ASGI server (development + runtime images) | Actively maintained (encode org) | Supported | httptools/uvloop extras not installed (pure-python extras) | click, h11 | BSD-3-Clause |
| `numpy` | unbounded minor | In-process cosine similarity (local vector adapter) | Actively maintained (NumFOCUS) | Supported (3.14 wheels available) | C-coded; CVEs are rare and tracked upstream | none | BSD-3-Clause |

## Test-only dependencies (`requirements_test.txt`)

| Dependency | Pin | Role | Maintenance | Python 3.14 | Vulnerability posture | License |
|---|---|---|---|---|---|---|
| `vcrpy` | unbounded minor, locked at install time | HTTP record/replay for outbound integrations | Actively maintained | Supported | No known advisories at adoption | MIT |

Rejected at planning (research.md § 9): `pytest` (plan mandates stdlib
`unittest`), `pytest-freezer` (unapproved), `mongomock` (real-MongoDB
integration tests are mandatory), `pytz` (forbidden by the UTC standard;
stdlib `zoneinfo` covers it), `arrow`/`pendulum` (stdlib coverage).

Dependency-selection policy: any new dependency requires (a) an active
maintenance signal, (b) Python 3.14 support, (c) a documented role, and
(d) compliance review against the constitution's dependencies policy.