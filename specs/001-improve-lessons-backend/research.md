# Research: Improve Lessons Backend

**Phase**: 0 — Resolve open decisions and lock technology choices
**Date**: 2026-10-13
**Source**: `specs/001-improve-lessons-backend/spec.md` (v1) + user-supplied implementation plan

This document captures the technical decisions that were still open after the
functional specification was ratified. Each decision is recorded with a
rationale, alternatives considered, and a verification note. The "Open
Decisions" section at the end enumerates the items that remain deferred and
must be approved before any task that depends on them starts.

## 1. Runtime and language

### Decision
- **Language**: Python 3.14.8.
- **Package manager**: `uv`.
- **Base image**: `python:3.14.8-bookworm-slim`.
- **Web framework**: `fastapi==0.142.2`.
- **HTTP client (async)**: `httpx`.
- **Test runner**: `unittest` (standard library), with
  `IsolatedAsyncioTestCase` for async test cases.
- **API test client**: `fastapi.testclient.TestClient`.
- **HTTP recording**: `vcrpy` (cassettes in `tests/vcr_cassettes/`).

### Rationale
The user-supplied implementation plan is explicit on every entry above and
the versions are valid as of 2026-10-13. `fastapi==0.142.2` was released on
2026-09-30 and lists Python 3.10–3.14 in its supported classifiers, so it is
compatible with Python 3.14.8. `httpx` is required by FastAPI's test client
internally and is the recommended async HTTP client for outbound integrations
(AI providers, email provider).

### Alternatives considered
- **Poetry / pip-tools / pip**: rejected because the plan mandates `uv`. `uv`
  is the de-facto standard fast installer/manager and produces reproducible
  lockfiles with `uv.lock`.
- **pytest**: rejected because the plan mandates `unittest`. The chosen
  runner is sufficient for the testing strategy in section 10 of the plan.
- **Starlette directly**: rejected because FastAPI adds pydantic validation
  and the dependency-injection surface the spec depends on.

### Verification
- FastAPI 0.142.2 PyPI metadata confirms `requires_python >= 3.10` and
  Python 3.14 classifier support.
- Pydantic 2.9+ is a transitive dependency of FastAPI 0.142.2 and is
  Python 3.14-compatible.

## 2. Persistence: MongoDB and the async driver

### Decision
- **Primary database**: MongoDB. 100% of functional data lives here. It is the
  authoritative source of truth; nothing else is.
- **Driver**: `pymongo` (latest 4.18.x) using its **native async API**
  (`AsyncMongoClient`), not Motor.
- **Local development**: MongoDB running in Docker, exposed through
  `compose.yaml`.

### Rationale
The user-supplied plan mandates MongoDB as the only data store. Pymongo 4.18.3
explicitly supports Python 3.14 and provides a native async API that replaces
Motor. Motor 3.7.1 is scheduled for deprecation in May 2026, so adopting
PyMongo's async API now avoids a forced migration in the first year of the
project.

### Alternatives considered
- **Motor 3.7.1**: rejected because of the upcoming deprecation. Pymongo
  Async is the recommended successor.
- **Beanie / ODMantic (ODM libraries)**: rejected for the initial release.
  Pydantic models are used at the API boundary; the persistence layer is
  encapsulated behind ports and adapters, so introducing an ODM would add a
  layer without changing the contract.
- **Direct MongoDB access from services**: explicitly forbidden by the
  plan. All access goes through `app/adapters/persistence/mongodb/`
  implementing interfaces declared in `app/core/ports/`.

### Verification
- Pymongo 4.18.3 PyPI metadata confirms `requires_python >= 3.9`, Python 3.14
  classifier support, and an asyncio API.

## 3. Vector persistence

### Decision
- **Vector store**: MongoDB Vector Search (`$vectorSearch`).
- **Data model**: original summaries are persisted in full in MongoDB; they
  are then chunked, embedded, and the chunks are stored as derived data in
  the same database. The vector representation never replaces the original
  summary.
- **Chunk metadata (mandatory)**: parent summary ID, owner user ID,
  filter/retrieval fields, source content version, reindex/removal flags.

### Rationale
The user-supplied plan makes MongoDB Vector Search the proposed solution.
Because `$vectorSearch` is an Atlas-only feature, the local development
environment will need an explicit posture. The decision for the initial
release is to run MongoDB locally and to implement a **port abstraction**
for vector search with two adapters:
1. `MongoDBAtlasVectorSearchAdapter` — the production adapter against
   `$vectorSearch`.
2. `InMemoryVectorSearchAdapter` — the local-development / unit-test
   adapter that performs cosine similarity over in-process numpy arrays.
The chunking, embedding, retrieval, and ranking code paths live entirely
behind the port and are therefore identical for both adapters.

### Alternatives considered
- **pgvector / PostgreSQL**: rejected because the plan mandates MongoDB as
  the single source of truth. Splitting the persistence stack would
  conflict with the constitution's "Separation of Responsibilities" and
  "Data Integrity" principles.
- **Pinecone / Weaviate / Milvus / Qdrant**: rejected for the same reason
  (single source of truth) and because they introduce a new network
  dependency for local development.
- **Local-only `mongosh` Atlas emulation**: rejected because there is no
  usable open-source emulation of `$vectorSearch` for self-hosted MongoDB.

### Open decision
- **Embedding model**: deferred. The plan lists it as an open decision.
  The selected adapter must support swapping the model without code
  changes outside the embedding adapter (see Section 6).
- **Chunking strategy**: deferred. The plan lists it as an open decision.
  Initial scope: sentence-aware chunking with configurable max token
  count and overlap, validated against Spanish/English bilingual summaries.
- **Vector index configuration**: deferred (defer-to-Atlas-deployment
  step). The local adapter does not need an index.

### Verification
- MongoDB Atlas documentation confirms `$vectorSearch` exists, requires
  Atlas, supports the `filter` pre-filtering pattern needed for
  per-user isolation, and returns `vectorSearchScore` for ranking.

## 4. AI architecture: RAG and LangGraph

### Decision
- **RAG flow**: persist summary → split into chunks → generate embeddings →
  store and index chunks → retrieve relevant chunks when a contextual
  query is processed → supply to the model → validate and persist output.
- **Workflow orchestration**: LangGraph is used wherever the workflow
  requires explicit state, branching, conditional execution, or multi-step
  coordination. Generation and evaluation are logically independent and
  MUST NOT bypass the approval gate.
- **Generation and evaluation as separate, non-shared-prompt models**:
  fixed per the constitution.

### Rationale
The user-supplied plan mandates RAG and LangGraph. The constitution (Principle
II) makes the two-model generation/evaluation workflow non-negotiable, and
LangGraph is the only mainstream Python library that gives explicit control
over that state machine (generation → evaluation → corrective loop → bound
enforcement).

### Alternatives considered
- **Direct calls in a single async function**: rejected because the corrective
  loop, retry bound, transient-failure absorption, and audit logging require
  branching and state that become hard to test in a single function.
- **Custom state machine on top of asyncio**: rejected because LangGraph
  already provides exactly this with declarative graph definitions and
  checkpointing.

### Provider decision (approved, T119)
- **Provider family**: **Ollama** (native API `POST /api/chat`), serving
  two DIFFERENT models — `minimax-m3.1-flash:cloud` for generation and
  `glm-5.3-flash:cloud` for evaluation. Both are `:cloud` models: Ollama
  proxies them to the provider's cloud, so the models do not run on the
  host's hardware.
- **Model identifiers are configuration, not code**: `AI_PROVIDER`,
  `AI_BASE_URL`, `AI_GENERATION_MODEL`, `AI_EVALUATION_MODEL` and the
  token budgets are environment variables with per-environment overrides.
  The `ContentGenerator` / `ContentEvaluator` ports stay provider-agnostic,
  so another provider can be added later without touching the services.
- **Embeddings**: still the deterministic hash (`DeterministicEmbeddingProvider`).
  Known pending item, documented in `docs/constitution_compliance.md`; the
  real embedding adapter drops in behind the same port.
- **Why not the Anthropic SDK**: the models are not Claude models. Calling
  the Anthropic SDK against a third-party provider's endpoint is not the
  provider's contract; the native Ollama API is. The native API is also
  measurably more reliable here: it honours `format: "json"`, while the
  Anthropic-compatible proxy silently discarded the equivalent field.
- **HTTP client**: `niquests` in synchronous mode, wrapped in
  `asyncio.to_thread` (the house pattern for synchronous clients). The
  reason is test coverage, not latency: vcrpy intercepts the standard
  `urllib3`, and niquests' async mode drives `urllib3-future` under an
  internal alias that vcrpy does not patch, so the async mode would put
  the test suite on the network. See `docs/dependency_evaluation.md`.
- **Retry and recovery**: the corrective loop's bound is shared — a
  transient provider failure consumes one attempt of the same bound as a
  corrective revision (A-17: no separate transient-failure counter), so
  the provider is called at most `bound` times. Permanent failures
  (unknown model, invalid request) leave the loop at once.

### Open decisions (require approval before implementation)
- **Chunking algorithm, chunk size, and overlap**.
- **Retrieval and ranking strategy** (top-k, MMR, score threshold, recency
  weighting).
- **Context size and token limits** per provider.
- **LangGraph workflow topology** (state shape, nodes, edges, branches).
- **Retry and recovery policies** (backoff, jitter, dead-letter handling).

## 5. Docker image strategy

### Decision
- **Three explicit build targets** in the single `Dockerfile`:
  - `dev` — development and debugging. **Not** for production.
  - `test` — automated testing and test dependencies. **Not** for
    production.
  - `runtime` — application and runtime dependencies only. Production
    releases use this target.
- **Runtime user**: non-root, UID 1000.
- **Environment**: `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1`.
- **Image tags**: stage-identifying (e.g., `improve-lessons-backend:dev`,
  `improve-lessons-backend:test`, `improve-lessons-backend:runtime`) plus
  version-identifying (semver or git SHA). Production deployment
  references an immutable digest.
- **No test code or `requirements_test.txt` in the runtime image**.

### Rationale
Direct enforcement of the user-supplied plan. The build pipeline MUST
validate image contents (e.g., a smoke test that asserts
`requirements_test.txt` is absent from the runtime image) because target
names and tags do not in themselves guarantee separation.

### Verification approach
- A CI job that builds each target and runs an image-content check (file
  inventory + entrypoint test).
- Runtime image must boot, expose the FastAPI app, and respond 200 on
  `/health`.

## 6. Docker Compose, LocalStack, and secret management

### Decision
- **`compose.yaml` services**: `mongodb`, `localstack`, and the FastAPI
  backend.
- **LocalStack** emulates AWS Secrets Manager.
- **Application configuration boundary**: `app/core/config/` exposes a
  `SecretProvider` port. The local adapter uses LocalStack; the production
  adapter uses the real AWS Secrets Manager client. Business logic does
  not import the AWS SDK directly.
- **No real credentials** in Dockerfiles, application images, or the
  repository. Local-only dummy values are versioned only when they cannot
  grant access to real external resources (LocalStack endpoints, dummy
  keys prefixed with `dummy-`).
- **`init.sh`** orchestrates the environment: verify Docker and Compose,
  start MongoDB and LocalStack, wait for health, initialize local secrets,
  validate mandatory secrets, then start the backend.
- **`scripts/init-localstack.sh`** creates and validates the local
  secrets.

### Rationale
Direct enforcement of the user-supplied plan. The configuration boundary
keeps the application portable and the test suite honest (tests can use a
fake `SecretProvider` without LocalStack).

### Open decision
- **Local secret inventory and values**: deferred. The init script
  defines a list; the exact keys and dummy values are listed in
  `tasks.md` once the AI provider decisions are made.

## 7. Authentication and authorization

### Decision
- **Authentication**: account-bound credentials over HTTPS, implemented
  behind a port in `app/core/ports/auth.py`. The exact mechanism
  (email+password, magic link, OAuth) is left to a dedicated approval
  step; the port contract is fixed now.
- **Authorization**: every request that reads or mutates a user's data is
  authorized against the requesting user's identity at the application
  layer, with a per-collection ownership filter at the persistence layer
  (defense in depth).
- **Object-level access control**: every entity that belongs to a user
  has an `owner_user_id` and a database-level filter that scopes reads
  and writes to that user.

### Rationale
The user-supplied plan lists "Authentication and authorization" as an open
decision. The port-first approach lets us lock the contract now and defer
the implementation choice (e.g., JWT, session cookies) to a single
subsequent approval without touching the rest of the codebase.

### Verification
- Per FR-082/083, every request to a user-protected endpoint is
  authenticated and authorized; cross-user access is rejected.
- Every collection in the data model has a user-scoped read/write path.

## 8. Logging and error handling

### Decision
- **Logger configuration**: `app/utils/logging.py` configures a
  project-specific logger with format
  `%(asctime)s | %(levelname)s | %(name)s | %(message)s`, `propagate=False`.
- **Helpers**: `report_error` and `report_info` functions, used from
  application code instead of `print()`.
- **Prohibition**: no `print()` in `app/`. No credentials, secrets, or
  excessive learning content in logs.

### Rationale
Direct enforcement of the user-supplied plan. `propagate=False` prevents
double-logging when a parent logger is also configured.

## 9. Testing strategy

### Decision
- **Runner**: `unittest` (standard library). Test discovery:
  `python -m unittest discover -s tests`.
- **Layered tests**:
  - Domain/strategies: unit tests.
  - Services: unit tests with `mock.patch` for adapters.
  - MongoDB adapters: real integration tests against an isolated MongoDB
    (use a unique database name per test run).
  - API endpoints: `fastapi.testclient.TestClient` against the FastAPI
    app, with adapters replaced by fakes.
  - External HTTP integrations: VCR cassettes (VCR records and replays;
    it does not replace MongoDB integration tests).
  - Idempotency: repeated and concurrent operation tests.
  - AI workflows: approval, failure, and retry tests, including the
    bounded corrective loop and transient-failure absorption.
  - Vector retrieval: relevance, filtering, and per-user isolation tests.
  - Secret initialization: repeatability and missing-secret tests.
  - Docker releases: image-content and dependency validation.

### Rationale
Direct enforcement of the user-supplied plan. VCR is explicitly limited
to HTTP interactions; real MongoDB integration tests are mandatory.

## 10. Work tree and module boundaries

### Decision
- The work tree in the user-supplied plan is the authoritative layout.
  Directories are created only when an approved task requires them.
- **Module boundaries** (enforced by import direction):
  - `app/api/` may import from `app/core/`, `app/services/`, `app/dtos/`,
    and `app/utils/`. It MUST NOT import from `app/adapters/`.
  - `app/services/` may import from `app/core/`, `app/dtos/`, and
    `app/utils/`. It MUST NOT import from `app/api/` or `app/adapters/`.
  - `app/adapters/` may import from `app/core/`, `app/dtos/`, and
    `app/utils/`. It MUST NOT import from `app/api/` or `app/services/`.
  - `app/core/` depends only on standard library and explicitly
    declared third-party packages (e.g., pydantic).
- The hexagonal-style split (`core/ports` + `adapters/`) is the only
  architectural layering. New layers require explicit approval.

### Rationale
Direct enforcement of the user-supplied plan. The import-direction rule
prevents the most common form of architectural drift: services calling
adapters or APIs.

## 11. Date and time handling — Mandatory UTC Standard

### Decision
- **Time-zone handling is centralized** in `app/core/time/`. The module
  exposes `now_utc()`, `parse_iso_to_utc(value)`,
  `to_utc_instant(value)`, `require_aware_utc(value)`, and a
  Pydantic-compatible `AwareDatetime` annotation bound to UTC.
- **Storage**: every persisted datetime is a timezone-aware UTC
  `datetime` stored as a MongoDB BSON `Date` (UTC by definition). The
  MongoDB adapter raises on a naive value before any insert or update.
- **API serialization**: the Pydantic `AwareDatetime` annotation
  serializes to ISO 8601 with the `Z` suffix (e.g.,
  `2026-10-13T14:30:00Z`). Explicit offsets are not emitted.
- **Input validation**: incoming timestamps with explicit offsets are
  accepted and normalized to UTC. Naive timestamps are rejected with
  `400 Bad Request` and `error.code = "invalid_timestamp"`. Local
  wall-clock fields (e.g., `start_time: "07:00"`) are stored as
  `HH:MM` strings and are not treated as instants.
- **External integrations**: datetimes received from external services
  (AI provider, email provider, vector search) are normalized to UTC at
  the adapter boundary. Datetimes sent to external services are encoded
  in UTC.
- **Logging**: the logging configuration emits the `asctime` in UTC
  with the `Z` suffix regardless of the host's local time zone.
- **Static enforcement**: a unit test fails the build if `app/`
  contains `datetime.now(` without an explicit `tz=`, `import pytz`,
  or `astimezone(` to a non-UTC zone outside `app/core/time/`.
- **Test coverage**: tests cover UTC normalization, naive-timestamp
  rejection, daylight-saving transitions for users in `America/Bogota`
  and similar zones, and BSON `Date` round-tripping.

### Rationale
The "Date and Time Handling — Mandatory UTC Standard" (an amendment to
the user-supplied plan) makes UTC the system-wide standard. Centralizing
the helpers and the Pydantic annotation in `app/core/time/` gives every
module a single import path to satisfy the rule; the static test makes
violations unreviewable rather than unreviewed.

### Alternatives considered
- **`arrow` / `pendulum`**: rejected for the initial release. They add
  a dependency that the standard library already covers with
  `datetime.timezone.utc`, `zoneinfo`, and Pydantic v2's
  `AwareDatetime`. They can be introduced later if the need arises,
  but doing so would require a separate approval per the constitution's
  dependency-selection policy.
- **Storing timestamps as ISO 8601 strings**: rejected. BSON `Date` is
  UTC by definition, supports range queries and time-based indexes
  natively, and avoids string-parse failures in aggregation pipelines.
- **Per-tz serialization at the API edge**: rejected. UTC at the API
  edge is the documented standard; per-tz display is a future
  presentation-layer concern that MUST NOT change the storage or API
  contract.

### Verification
- `python -m unittest discover -s tests` exercises every rule in this
  section.
- The `quickstart.md` §9 fixtures are run as part of the smoke test.
- The runtime image validation in `quickstart.md` §9.5 asserts that
  the runtime container emits a Z-suffixed UTC log line.

## Open decisions (deferred until explicit approval)

The following items are still open and MUST be approved before any task
that depends on them is started. None is an approved implementation
requirement.

1. Exact MongoDB collection names and indexes.
2. Chunking algorithm, chunk size, and overlap.
3. Embedding model and vector index configuration.
4. RAG retrieval and ranking strategy.
5. AI providers and model configuration (generation, evaluation, embedding).
6. LangGraph workflow topology.
7. Authentication and authorization implementation mechanism (port is
   fixed; concrete mechanism is not).
8. Asynchronous workers and scheduling (queue, scheduler, retry policy).
9. Local secret inventory and initialization values.
10. Production infrastructure and secret management.
11. Data retention and deletion policies.
12. Formatting, linting, and security-scanning tools.
13. CI/CD implementation and release promotion rules.

## References

- User-supplied implementation plan (the technical input for this research).
- Constitution at `.specify/memory/constitution.md`.
- Functional specification at `specs/001-improve-lessons-backend/spec.md`.
- PyPI metadata for `fastapi 0.142.2`, `pymongo 4.18.3`, `motor 3.7.1`,
  `langgraph 1.2.15` (verified 2026-10-13).
- MongoDB Atlas documentation on `$vectorSearch` (verified 2026-10-13).
