# Implementation Plan: Improve Lessons Backend

**Branch**: `001-improve-lessons-backend` | **Date**: 2026-10-13 |
**Spec**: [spec.md](./spec.md)

**Input**: Feature specification from
`/specs/001-improve-lessons-backend/spec.md`, the user-supplied technical
implementation plan, and the project constitution at
`/specify/memory/constitution.md`.

## Summary

`improve_lessons_backend` is a multi-user FastAPI backend that helps
English learners build consistent study habits, document what they have
learned, reinforce that knowledge through personalized reading and
writing practice, and progressively develop their skills. The system
implements a two-model AI workflow (generation + independent evaluation)
backed by a single MongoDB source of truth and a port-and-adapter
architecture that isolates business logic from persistence, AI, and
notification providers. The initial release is text-based and ships with
Docker-based local development (MongoDB, LocalStack, FastAPI) and
reproducible CI.

The primary technical approach is:

- **Hexagonal layering** (`core/ports` + `adapters/`) so that
  persistence, AI, and notifications are interchangeable.
- **MongoDB as the single source of truth** with Pymongo Async (not
  Motor, which is being deprecated in May 2026).
- **MongoDB Atlas Vector Search** in production with a local in-process
  adapter behind the same port for development and unit tests.
- **RAG + LangGraph** for the AI workflow, with separate generation and
  evaluation models, a bounded corrective loop, and explicit
  transient-failure absorption.
- **Three-stage Dockerfile** (`dev`, `test`, `runtime`) with content
  validation of the runtime image.
- **LocalStack** for local secret management behind a configuration
  boundary that decouples business logic from any specific provider.

The plan resolves every technology decision that was open in the
specification's "Assumptions" section, with two small deferrals
documented in the "Open Decisions" section below (AI providers and the
embedding/chunking strategy).

## Technical Context

**Language/Version**: Python 3.14.8.

**Primary Dependencies**:
- `fastapi==0.142.2` (web framework; verified compatible with Python 3.14)
- `pymongo>=4.18,<5.0` (async MongoDB driver, replaces Motor)
- `pydantic>=2.9` (transitive via FastAPI; reused for DTOs)
- `httpx` (async HTTP client for outbound integrations)
- `langgraph` (AI workflow orchestration)
- `vcrpy` (HTTP recording for tests)
- `unittest` (standard-library test runner)
- `fastapi.testclient.TestClient` (API tests)
- `uv` (package manager; produces `uv.lock`)

**Storage**: MongoDB (single source of truth). Vector embeddings are
stored as derived data in the same database, in a separate collection
with a vector index when Atlas is available; the local adapter uses
in-process numpy arrays.

**Testing**: `python -m unittest discover -s tests`. Async cases use
`IsolatedAsyncioTestCase`. MongoDB integration tests run against an
isolated MongoDB instance; HTTP integrations use VCR cassettes.

**Target Platform**: Linux server (containerized via Docker; base image
`python:3.14.8-bookworm-slim`).

**Project Type**: Web service (FastAPI backend).

**Performance Goals**: 100% of submission-to-material pipeline must
complete (or fail with a clear error) within the bounded corrective
loop. Local development must boot the stack in under 5 minutes from a
clean state. Specific throughput targets are deferred to the operations
plan (out of scope for this plan).

**Constraints**:
- No real credentials committed; LocalStack-only secrets in version
  control.
- Runtime Docker image MUST NOT contain test code or test dependencies.
- The application MUST NOT access MongoDB outside the persistence
  adapters.
- The two-model generation/evaluation workflow MUST NOT bypass the
  approval gate (constitution principle II).
- **All persisted timestamps represent UTC instants. Naive datetimes
  MUST NOT be used to represent instants anywhere in the system.
  See "Mandatory Standards § Date and Time Handling" below.**

**Scale/Scope**: Initial release targets a small number of users (the
first cohort). Horizontal scaling and sharding are deferred to the
operations plan.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Constitution principle | Plan compliance |
|---|---|
| **I. CEFR-Aligned Content Difficulty** | Enforced by `content_evaluations.criterion_assessments` (vocabulary, grammar, sentence length, reading demands, writing demands, relevance) and the "do not exceed CEFR by more than one level" rule in `app/services/recommendations/`. |
| **II. Two-Model Content Generation and Evaluation** | The `content_generation` and `content_evaluation` collections are owned by separate ports (`app/core/ports/content_generator.py` and `app/core/ports/content_evaluator.py`). No shared prompts. Bounded corrective loop in `app/services/content/corrective_loop.py`. |
| **III. Personalization from Documented Learning History** | `summary_chunks` carry `owner_user_id` and `summary_id` metadata; RAG retrieval filters by `owner_user_id`; `app/services/content/generation_inputs.py` builds the prompt context from the user's history slice. |
| **IV. Reliable Learning Records and Submission Integrity** | `daily_summaries` is append-only (FR-024a); `submission_status` is computed at insert time and stored on the document. On-time/late derivation in `app/services/sessions/derive_submission_status.py` uses the user's time zone. |
| **V. Activity Metrics Are Not Proficiency Evidence** | The progress endpoint returns three explicit dimensions (reading, writing, consistency) with disclaimers (FR-071, FR-072, SC-013). The progress DTO does not contain any field that could be interpreted as a proficiency score. |
| **VI. Time-Zone Consistent Scheduling** | All time-zone handling lives in `app/core/time/` and is applied at the application boundary. The MongoDB adapter stores UTC ISO 8601; the user's `time_zone` is read on every computation. The schedule-expansion service uses the user's tz. |
| **VII. Progressive, Evidence-Based Difficulty Adaptation** | Recommendations live in `app/services/recommendations/`; the service consults the user's CEFR level and recent history to produce a challenge that does not exceed CEFR + 1 (FR-075). |
| **VIII. User Motivation and Positive Reinforcement** | `recognitions` are produced by `app/services/motivation/recognitions.py`; the recommendations service applies the "gradual difficulty" rule (FR-077). |
| **IX. Separation of Responsibilities** | The plan enforces a strict import direction (see Project Structure § Module boundaries). `app/core/` has no third-party dependencies beyond pydantic; `app/services/` does not import from `app/adapters/`. |
| **X. Observability and Failure Containment** | The audit log (`audit_events`) is required for every privileged operation (FR-084–FR-086). The corrective loop's bound is enforced in the service layer; on bound exhaustion, the workflow records the failure and does not surface unapproved content. |

**Compliance verdict**: PASS. No constitution principle is violated. No
complexity-tracking entries are required.

## Mandatory Standards

This section lists system-wide standards that are non-negotiable across
every module. Each standard binds the implementation; the task list
must include a verification step for each rule.

### Date and Time Handling — Mandatory UTC Standard

UTC is the system-wide standard for storing, exchanging, and
calculating timestamps. Any future requirement to display dates in a
user's local time zone MUST be handled explicitly at the presentation
boundary and MUST NOT change the UTC persistence standard.

The rules below are mandatory and override any conflicting local
convention. They bind storage, application logic, API contracts, input
validation, external integrations, logging, and testing.

| # | Area | Rule |
|---|---|---|
| 1 | **Storage** | All persisted timestamps MUST use UTC. MongoDB datetime values MUST be timezone-aware UTC datetimes at the application boundary and stored using MongoDB's UTC datetime representation (BSON `Date` is UTC by definition; the application never hands MongoDB a naive or non-UTC datetime). |
| 2 | **Application logic** | All internal date and time calculations MUST use UTC-aware datetime objects (`datetime.timezone.utc` or `datetime.UTC` in Python 3.11+). Naive datetime objects MUST NOT be used to represent instants anywhere inside `app/`. The only place a naive datetime is acceptable is local wall-clock fields (e.g., `start_time`, `end_time` on `schedules`), which are stored as `HH:MM` strings and never converted to instants without a time zone. |
| 3 | **API contracts** | All API timestamps MUST be expressed in UTC using ISO 8601 format with the `Z` suffix, e.g., `2026-10-13T14:30:00Z`. The `Z` is mandatory; explicit offsets such as `+00:00` are NOT accepted in API responses. Pydantic serializers for `datetime` MUST be configured to emit the `Z` suffix and reject naive values. |
| 4 | **Input validation** | Incoming timestamps MUST be validated. Timestamps with explicit UTC offsets (e.g., `2026-10-13T10:30:00-04:00`) MAY be accepted, but MUST be normalized to UTC before any processing or persistence. Naive timestamps (e.g., `2026-10-13T10:30:00` with no offset) MUST be rejected with a `400 Bad Request` unless the endpoint explicitly defines a different interpretation (e.g., a `date` field for local calendar dates). |
| 5 | **External integrations** | Dates received from external services (AI provider, email provider, vector search) MUST be normalized to UTC at the adapter boundary when they represent instants. Dates sent to external services MUST be encoded in UTC. |
| 6 | **Logging** | Log timestamps MUST use UTC. The logging configuration in `app/utils/logging.py` MUST emit a `Z`-suffixed ISO 8601 UTC timestamp as the `asctime` value, regardless of the host's local time zone. |
| 7 | **Testing** | Tests MUST cover (a) UTC normalization of incoming timestamps with explicit offsets, (b) rejection of naive timestamps at API and adapter boundaries, (c) correct handling of daylight-saving transitions where relevant (e.g., a user whose time zone is `America/Bogota` and a session that crosses a DST boundary), and (d) that persisted values are stored as UTC instants. |
| 8 | **Consistency** | No component, service, adapter, or API endpoint may introduce an implicit local time zone when handling timestamps. `datetime.now()` without a `tz` argument is forbidden inside `app/`; the only allowed call is `datetime.now(UTC)`. `pytz.localize`, `astimezone()` to a local zone, and any other silent local-time conversion are forbidden inside business code. |

**Acceptance criteria**:

- All persisted timestamps represent UTC instants.
- All API timestamps follow the documented UTC format with the `Z` suffix.
- Naive datetimes cannot enter internal processing without explicit
  validation; the API rejects them with a `400 Bad Request` and the
  application layer rejects them at module boundaries.
- UTC normalization is applied consistently across application services
  and persistence adapters.
- Automated tests verify time-zone-aware behavior and UTC normalization
  for API, service, and adapter layers.

**Implementation reference points** (recorded in `research.md`
amendments and tracked by `tasks.md`):

- A shared `app/core/time/` module providing `now_utc()`,
  `parse_iso_to_utc(value)`, `to_utc_instant(value)`, and a
  `require_aware_utc(value)` helper that raises on naive datetimes.
- A custom Pydantic v2 `AwareDatetime` annotation bound to UTC, used
  by every API request and response model that carries a timestamp.
- A `before` Pydantic validator on every request model that accepts a
  timestamp, normalizing offsets and rejecting naive values.
- A logging formatter that emits the `Z` suffix.
- A static lint rule (or unit test) that fails the build if
  `datetime.now(` or `pytz` or `astimezone()` to a local zone appears
  in `app/` outside `app/core/time/`.

### Senior-Level Engineering Criteria — Non-Negotiable

Every piece of code written in this project MUST meet senior-developer
standard. The rules below are stated as general criteria; the AWS client
configuration items are concrete examples, not the whole scope — the
criteria as a whole bind all code written now and in the future.

| # | Principle | Rule |
|---|---|---|
| 1 | **DRY (Don't Repeat Yourself)** | Suggested code MUST NOT violate DRY. A single source of truth shared by all usage sites; duplication is a defect. *Example (binding):* the AWS client kwargs dict lives only in `app/core/config/settings.py` (`LOCALSTACK_AWS_CREDENTIALS` + `aws_client_credentials`) — duplicating it in adapters or concrete clients is forbidden. This example illustrates the general criterion, which applies to any code written. |
| 2 | **Environment decides environment-specific configuration** | When a configuration is specific to an environment, the decision input is the environment (`APP_ENV`), not a URL or any incidental value: `APP_ENV=development` (LocalStack parameterization; the `endpoint_url` lives inside the shared dict) vs. every other environment (empty dict, basic client). |
| 3 | **Production uses IAM — design for local-vs-cloud parity** | Every AWS (or private-cloud) client is written without explicit credentials or emulator artifacts: in production the IAM credential chain resolves auth and the region resolves the endpoint. No round-trips to Secrets Manager to authenticate SDK clients. Any new external-service implementation MUST contemplate both scenarios — local/emulated and real cloud — designed in together, so the same code runs in either environment. |
| 4 | **`__init__.py` never carries functional code** | Package `__init__` files are import-only re-export facades (+ `__all__`). All definitions (Settings, constants, helpers) live in their own modules (e.g., `settings.py`). Defining Settings or any helper inside `__init__` is a bad practice and breaks project legibility. |
| 5 | **Config → composition root → adapters** | Environment-dependent decisions are made exactly once, in the composition root (`main.py::Container`), and injected pre-computed into adapters; adapters contain no environment-selection logic. Future AWS clients are integrated as `boto3.client("<service>", **aws_settings)`. |

**Acceptance criteria**:

- No duplicated configuration source for AWS (or any shared) client
  initialization; the shared dict + helper is the only source.
- Client-flavor selection (local emulated vs. real cloud) is driven by
  `APP_ENV` and only by `APP_ENV`.
- No SDK client in the codebase passes hardcoded credentials; production
  relies on the IAM credential chain, and Secrets Manager stores only
  application secrets.
- `app/**/__init__.py` files contain imports and `__all__` only; a code
  review against this plan rejects any functional code there.
- Composition-root injection is the only place where environment-specific
  client parameters are computed.

## Project Structure

### Documentation (this feature)

```text
specs/001-improve-lessons-backend/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── README.md        # API contracts
├── checklists/
│   └── requirements.md  # Spec quality checklist
├── spec.md              # Functional specification
└── tasks.md             # Phase 2 output (/speckit-tasks command — NOT created by /speckit-plan)
```

### Source Code (repository root)

The work tree is the authoritative layout from the user-supplied
implementation plan. Directories are created only when an approved task
in `tasks.md` requires them.

```text
improve_lessons_backend/
├── app/
│   ├── __init__.py
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       ├── requests/
│   │       └── responses/
│   ├── core/
│   │   ├── ports/
│   │   └── strategies/
│   ├── services/
│   ├── adapters/
│   │   ├── persistence/
│   │   │   └── mongodb/
│   │   └── external/
│   │       ├── ai/
│   │       └── notifications/
│   ├── dtos/
│   └── utils/
├── scripts/
│   └── init-localstack.sh
├── tests/
│   ├── adapters/
│   ├── api/
│   ├── core/
│   ├── services/
│   ├── integration/
│   ├── utils/
│   ├── commons/
│   └── vcr_cassettes/
├── Dockerfile
├── compose.yaml
├── init.sh
├── main.py
├── requirements.txt
├── requirements_test.txt
├── .dockerignore
├── .gitignore
└── README.md
```

**Structure Decision**: The hexagonal-style layering (`core/ports` +
`adapters/`) is the only architectural layering. New layers require
explicit approval and a corresponding complexity-tracking entry.

**Module boundaries (enforced by code review and import-lint)**:

| Module | May import from | MUST NOT import from |
|---|---|---|
| `app/api/` | `app/core/`, `app/services/`, `app/dtos/`, `app/utils/` | `app/adapters/` |
| `app/services/` | `app/core/`, `app/dtos/`, `app/utils/` | `app/api/`, `app/adapters/` |
| `app/adapters/` | `app/core/`, `app/dtos/`, `app/utils/` | `app/api/`, `app/services/` |
| `app/core/` | standard library, pydantic | `app/api/`, `app/services/`, `app/adapters/` |

These rules are enforced by the test suite (a static import-direction
test) and by code review.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be
> justified.** No violations identified. The table is empty by design.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| _(none)_  |            |                                     |

## Decisions captured in `research.md`

The following technology decisions are recorded in detail in
[`research.md`](./research.md):

- Python 3.14.8, FastAPI 0.142.2, `uv`, Pymongo Async (not Motor),
  MongoDB Atlas Vector Search with an in-process local adapter, RAG +
  LangGraph, three-stage Dockerfile, LocalStack for secrets, `unittest`
  with VCR cassettes, hexagonal layering with strict import direction.

## Open Decisions (deferred)

The following items remain open and MUST be explicitly approved before
any task that depends on them is started. None is an approved
implementation requirement.

1. **Exact MongoDB collection names and indexes** (see `data-model.md`
   for the index classes that are required; the concrete names and
   definitions are produced in `tasks.md`).
2. **Chunking algorithm, chunk size, and overlap** for `summary_chunks`.
3. **Embedding model and vector index configuration** (production Atlas
   adapter).
4. **RAG retrieval and ranking strategy** (top-k, MMR, score
   thresholds).
5. **AI providers and model configuration** (generation, evaluation,
   embedding).
6. **LangGraph workflow topology** (state shape, nodes, edges,
   branches, retry policies).
7. **Authentication and authorization implementation** (port is fixed in
   `research.md` §7; the concrete mechanism is not).
8. **Asynchronous workers and scheduling** (queue, scheduler, retry
   policy).
9. **Local secret inventory and values** (placeholder names are listed
   in `quickstart.md`).
10. **Production infrastructure and secret management**.
11. **Data retention and deletion policies**.
12. **Formatting, linting, and security-scanning tools**.
13. **CI/CD implementation and release promotion rules**.

## How this plan is used downstream

- `/speckit-tasks` produces `tasks.md`, decomposing this plan into
  ordered implementation tasks. Each task references the spec, the
  constitution principles it satisfies, and the data model and
  contracts it consumes.
- The plan itself is **not** an implementation guide for code; it
  establishes the architecture, the boundaries, and the decisions that
  every task must respect. The actual code, indexes, and configuration
  values are produced in the implementation phase.
