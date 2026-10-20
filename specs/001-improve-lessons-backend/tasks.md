# Tasks: Improve Lessons Backend

**Input**: Design documents from `/specs/001-improve-lessons-backend/`
- `plan.md` (required) — architecture, technology stack, mandatory standards (incl. UTC).
- `spec.md` (required) — 13 user stories with priorities P1, P2, P3.
- `research.md` — technology research and decisions.
- `data-model.md` — MongoDB collection schema, validation rules, time-zone handling.
- `contracts/README.md` — HTTP API surface.
- `quickstart.md` — validation runbook.

**Prerequisites**: `plan.md` and `spec.md` are required. All other design
documents exist and are referenced from the relevant tasks.

**Tests**: The user-supplied plan requires unit tests for domain and
strategies, service-level unit tests with `mock.patch`, real MongoDB
integration tests for adapters, FastAPI TestClient tests for endpoints,
VCR cassettes for outbound HTTP, idempotency / concurrent-operation
tests, AI workflow approval/failure/retry tests, vector retrieval
relevance/filtering/isolation tests, secret-initialization
repeatability/missing-secret tests, and Docker image-content validation.
Test tasks are therefore generated for every user story.

**Organization**: Tasks are grouped by user story to enable independent
implementation and testing. The Foundational phase includes the UTC
standard (`plan.md` § Mandatory Standards), the core ports, the
MongoDB adapter skeleton, the secret provider, and the observability
scaffolding; it MUST be complete before any user-story work begins.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on
  incomplete tasks).
- **[Story]**: Which user story this task belongs to (e.g., `US1`,
  `US2`).
- Include exact file paths in descriptions.

## Path Conventions

This is a single FastAPI backend (web service) project. Per `plan.md`,
the source root is `app/` and the test root is `tests/`. All paths
below are project-relative.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, tooling, base image, and the
directory layout defined in `plan.md`.

- [X] T001 Create the project tree from `plan.md` § Project Structure
  (create `app/`, `app/api/v1/{endpoints,requests,responses}/`,
  `app/core/{ports,strategies}/`, `app/services/`,
  `app/adapters/{persistence/mongodb,external/{ai,notifications}}/`,
  `app/dtos/`, `app/utils/`, `scripts/`, `tests/{adapters,api,core,
  services,integration,utils,commons,vcr_cassettes}/`) and add empty
  `__init__.py` files where Python requires them.
- [X] T002 Create `requirements.txt` with pinned versions: `fastapi==
  0.142.2`, `pymongo>=4.18,<5.0`, `pydantic>=2.9`, `httpx`,
  `langgraph`, `uvicorn` (standard), and any additional packages
  verified compatible with Python 3.14.8 in `research.md`.
- [X] T003 [P] Create `requirements_test.txt` with pinned versions:
  `vcrpy`, `mongomock` (only if a chosen test pattern requires it;
  otherwise leave the file empty of test-only deps that MUST NOT ship
  in the runtime image), `pytest-freezer` only if approved.
- [X] T004 [P] Create `pyproject.toml` (or `uv.toml`) configuring `uv`
  as the package manager and the standard test command `python -m
  unittest discover -s tests` in the `[tool.uv]` block.
- [X] T005 [P] Create `.dockerignore` excluding `tests/`,
  `requirements_test.txt`, `.git/`, `.specify/`, `.claude/`, `*.md`
  except `README.md`, and other build-time-only paths.
- [X] T006 [P] Create `Dockerfile` with three explicit build targets
  per `plan.md` § Docker image strategy: `dev` (development and
  debugging), `test` (test dependencies, not for production), and
  `runtime` (runtime dependencies only, permitted for production). Use
  `python:3.14.8-bookworm-slim`, set `PYTHONDONTWRITEBYTECODE=1`,
  `PYTHONUNBUFFERED=1`, run as a non-root user with UID 1000, install
  with `uv`, never copy `requirements_test.txt` into the `runtime`
  target.
- [X] T007 [P] Create `compose.yaml` orchestrating three services:
  `mongodb` (MongoDB), `localstack` (LocalStack with the
  `secretsmanager` service enabled), and `backend` (built from the
  `dev` target, depends on healthy MongoDB and LocalStack). Health
  checks for MongoDB (`mongosh ping`) and LocalStack (`awslocal
  secretsmanager list-secrets`).
- [X] T008 [P] Create `scripts/init-localstack.sh` that creates the
  local secrets listed in `tasks.md` § Open Decisions / Local secret
  inventory placeholder, with `dummy-` prefixed values that cannot
  grant access to real external resources. The script MUST be
  idempotent: running it twice produces the same final state.
- [X] T009 [P] Create `init.sh` that verifies `docker` and `docker
  compose`, starts MongoDB and LocalStack, waits for both health
  checks, runs `scripts/init-localstack.sh`, validates that every
  mandatory secret exists, then starts the backend. Fails fast on
  any missing prerequisite.
- [X] T010 [P] Create `main.py` exposing the FastAPI application
  factory `create_app()` that wires the API router, the logging
  configuration, and the lifespan handler that opens and closes the
  MongoDB connection and the configured `SecretProvider`.
- [X] T011 [P] Create `README.md` documenting the prerequisites
  (Docker, `uv`), the standard commands (`./init.sh`, `python -m
  unittest discover -s tests`), the runtime image assertion, and
  links to `specs/001-improve-lessons-backend/{plan,spec,data-model,
  research,quickstart,contracts}.md`.

**Checkpoint**: The project tree exists, the runtime image builds
without errors, and `init.sh` brings up MongoDB and LocalStack with
the dummy secrets in place.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user
story can be implemented. Includes the UTC standard, the central
logging configuration, the secret provider boundary, the MongoDB
adapter skeleton, the import-direction lint, and the FastAPI
scaffolding.

**⚠️ CRITICAL**: No user story work can begin until this phase is
complete.

- [X] T012 [P] Implement `app/core/time/__init__.py` and
  `app/core/time/utc.py` with `now_utc()`,
  `parse_iso_to_utc(value)`, `to_utc_instant(value)`,
  `require_aware_utc(value)`, and a Pydantic-compatible
  `AwareDatetime` annotation bound to UTC. Every function MUST raise
  on naive datetimes; `parse_iso_to_utc` MUST reject naive strings
  with a `ValueError` whose message starts with `invalid_timestamp`.
- [X] T013 [P] Implement `app/utils/logging.py` per `plan.md` § 9 and
  `research.md` § 11: a project-specific logger with format
  `%(asctime)s | %(levelname)s | %(name)s | %(message)s`,
  `propagate=False`, `report_error` and `report_info` helpers, and an
  `asctime` formatter that emits UTC ISO 8601 with the `Z` suffix
  (e.g., `2026-10-14T14:30:00Z`).
- [X] T014 [P] Define every port in `app/core/ports/` as abstract
  base classes: `user_repository.py`,
  `user_profile_history_repository.py` (append-only log of profile
  changes per `data-model.md` `users_profile_history`), 
  `platform_repository.py`,
  `schedule_repository.py`, `session_repository.py`,
  `summary_repository.py`, `daily_material_repository.py`,
  `weekly_summary_repository.py`, `weekly_material_repository.py`,
  `monthly_summary_repository.py`, `monthly_material_repository.py`,
  `assistant_thread_repository.py`, `content_generation_repository.py`,
  `content_evaluation_repository.py`, `summary_chunk_repository.py`,
  `feature_availability_repository.py`, `audit_event_repository.py`,
  `secret_provider.py`, `clock.py` (returns a UTC datetime, for
  testing), `content_generator.py`, `content_evaluator.py`,
  `embedding_provider.py`, `vector_search.py`, `email_sender.py`,
  `auth.py` (returns the authenticated principal). Each port is
  a single abstract class with no third-party imports.
- [X] T015 [P] Implement `app/core/config/__init__.py` and
  `app/core/config/secret_provider.py` exposing a `SecretProvider`
  factory that returns the LocalStack adapter in development and a
  no-op / AWS adapter in production (the production adapter is a
  forward concern; the LocalStack adapter is the only required
  adapter for the initial release). The factory reads the
  configuration from environment variables; missing mandatory
  configuration produces an explicit configuration error and the
  process MUST refuse to start.
- [X] T016 [P] Implement `app/core/strategies/` with the initial
  strategy interfaces: `submission_status_strategy.py` (computes
  `on_time` vs `late` from the user's tz and the 30-minute window),
  `week_boundary_strategy.py` (Monday 00:00 → next Monday 00:00 in
  the user's tz), `month_boundary_strategy.py` (calendar month in
  the user's tz), and `recommendation_strategy.py` (CEFR + 1 bound,
  FR-075). Strategies depend only on `app/core/time/` and pydantic.
- [X] T017 Implement `app/adapters/persistence/mongodb/__init__.py`
  and `app/adapters/persistence/mongodb/client.py` with an async
  `MongoClient` wrapper built on Pymongo 4.18+ native async API (NOT
  Motor, per `research.md` § 2). The wrapper exposes a `database()`
  accessor and a `close()` method. The client MUST raise on startup
  if the connection cannot be established.
- [X] T018 [P] Implement `app/adapters/persistence/mongodb/mappers.py`
  with bidirectional mappers between domain entities and MongoDB
  documents. Every mapper applies the UTC invariant: documents are
  stored as BSON `Date` (UTC) and the mapper raises on a naive
  datetime before any write.
- [X] T019 [P] Implement `app/adapters/persistence/mongodb/
  repositories/` with one adapter per port (one file per repository
  listed in T014, including `user_profile_history_repository.py`).
  Every repository enforces `owner_user_id` filtering at the query
  level (defense in depth). Every repository uses the mappers from
  T018. The `user_profile_history_repository` adapter appends one
  row per change (the collection is append-only). Index definitions
  are produced as per-data-model.md "Indexes" in `tasks.md` § Open
  Decisions.
- [X] T020 [P] Implement `app/adapters/external/ai/local_vector_search.
  py` (in-process numpy cosine similarity over `summary_chunks`) and
  stub the `content_generator.py` / `content_evaluator.py` /
  `embedding_provider.py` adapters with a deterministic fake that
  satisfies the port contract and is used until the AI provider
  decisions in `research.md` § 4 are approved.
- [X] T021 [P] Implement `app/adapters/external/notifications/
  localstack_email_sender.py` (a fake `email_sender` that records
  the rendered message in memory for tests, plus a LocalStack SES
  adapter that uses the dummy secrets from `init-localstack.sh`).
  The fake MUST be the default in development so the test suite
  does not require network access.
- [X] T022 Implement `app/api/v1/__init__.py` and
  `app/api/v1/requests/` with a custom Pydantic v2 `AwareDatetime`
  type bound to UTC. Every request model that accepts a timestamp
  uses this type. Naive values are rejected with a `400 Bad
  Request` and `error.code = "invalid_timestamp"`. The Pydantic
  `before` validator normalizes explicit offsets to UTC.
- [X] T023 [P] Implement `app/api/v1/responses/` with the response
  models that emit timestamps in ISO 8601 with the `Z` suffix. The
  Pydantic serializer is configured globally so explicit offsets
  such as `+00:00` are not emitted.
- [X] T024 [P] Implement the global error handler in
  `app/api/v1/error_handlers.py` that produces the documented error
  envelope (`{ "error": { "code", "message", "details" } }`) and
  maps `invalid_timestamp` and other domain errors to the correct
  HTTP status codes per `contracts/README.md`.
- [X] T025 Implement `app/api/v1/router.py` and the empty endpoint
  skeletons in `app/api/v1/endpoints/` for every endpoint listed in
  `contracts/README.md`. The skeletons return `501 Not Implemented`
  until their user-story task is reached. The router is mounted
  under `/api/v1` in `main.py`.
- [X] T026 [P] Implement the static import-direction lint at
  `tests/core/test_import_direction.py` (per `plan.md` § Project
  Structure): the test fails if any module in `app/api/`,
  `app/services/`, or `app/adapters/` imports from a forbidden
  module, and if `app/core/` imports anything from `app/api/`,
  `app/services/`, or `app/adapters/`. The test is run as part of
  `python -m unittest discover -s tests`.
- [X] T027 [P] Implement `tests/core/test_no_implicit_local_time.py`
  (per `quickstart.md` § 9.3): the test fails the build if
  `datetime.now(` without an explicit `tz=` argument, `import pytz`,
  or `astimezone(` to a non-UTC zone appears in `app/` outside
  `app/core/time/`. The test is run as part of `python -m unittest
  discover -s tests`.
- [X] T028 [P] Implement the audit-event writer port and adapter in
  `app/core/ports/audit_event_repository.py` and
  `app/adapters/persistence/mongodb/repositories/
  audit_event_repository.py`. The adapter writes to the
  `audit_events` collection (per `data-model.md`) and MUST be
  available before any user-story task that performs a privileged
  operation.
- [X] T029 [P] Implement the test fixtures in `tests/commons/`:
  `mongo_isolated_database.py` (creates a unique database per test
  run, drops it on teardown), `vcr_config.py` (VCR cassette
  configuration), `fastapi_client.py` (TestClient factory that
  injects in-memory fakes for every adapter), and
  `dummy_user_factory.py` (creates a registered user, a platform,
  a schedule, and an on-time submission for re-use across tests).
- [X] T030 [P] Implement the `Idempotency-Key` middleware in
  `app/api/v1/dependencies/idempotency.py` and the supporting
  port + adapter in `app/core/ports/idempotency_store.py` and
  `app/adapters/persistence/mongodb/repositories/idempotency_store.py`.
  The middleware reads the `Idempotency-Key` request header on
  every write endpoint documented in `contracts/README.md`
  § Conventions; if a key is present, the middleware looks up
  the previously stored response and replays it verbatim, and
  if the key is unknown, it acquires a short-lived lease,
  forwards the request, and stores the final response. The
  store enforces a uniqueness constraint on `(owner_user_id,
  idempotency_key)` so two concurrent requests with the same
  key do not both reach the underlying service. The middleware
  is integrated with the request-handling chain in `app/api/v1/`
  before any write endpoint runs. The adapter stores the
  response in a dedicated `idempotency_keys` collection (TTL
  per `data-model.md` Conventions).

**Checkpoint**: `python -m unittest discover -s tests` is green for
the foundational tests; the runtime image boots; the static lint
tests fail loudly if the import direction or the no-implicit-local-
time rule is broken.

---

## Phase 3: User Story 1 — Register and Configure a Learning Profile (Priority: P1) 🎯 MVP

**Goal**: A new user can register, declare a CEFR level and time
zone, and review or update their profile. Every other story depends
on this.

**Independent Test**: Register a user with name, email, CEFR level,
and time zone; read the profile back; update the CEFR level; verify
the previous value is in `profile_history`.

- [X] T031 [P] [US1] Add integration tests in
  `tests/api/test_users.py` covering the user-journey acceptance
  scenarios from `spec.md` US-1: registration with all required
  fields; rejection of missing/invalid email; rejection of
  invalid CEFR; rejection of invalid time zone; profile update
  appends to `profile_history`; `GET /users/me` returns the
  authenticated user's profile.
- [X] T032 [P] [US1] Implement the user domain entity in
  `app/core/entities/user.py` with `name`, `preferred_name`,
  `email`, `cefr_level` (enum: `A1`, `A2`, `B1`, `B2`, `C1`, `C2`),
  `time_zone` (IANA tz identifier), `created_at`, `updated_at`,
  `version`. The entity is a pydantic model.
- [X] T033 [US1] Implement the `user_repository` adapter
  integration tests in `tests/integration/test_user_repository.py`
  against a real MongoDB (per `plan.md` § 10): unique email
  enforcement; time-zone validation; `profile_history` append on
  update; `owner_user_id` is always set on insert.
- [X] T034 [US1] Implement the `user_service` in
  `app/services/user_service.py` exposing `register`, `get_me`,
  `update_me`, and `append_profile_history`. The service enforces
  the validation rules in `data-model.md` (RFC-5322 email; CEFR
  enum; IANA tz via `zoneinfo`).
- [X] T035 [US1] Implement the auth dependency in
  `app/api/v1/dependencies/auth.py` and the registration / login /
  logout / me endpoints in `app/api/v1/endpoints/auth.py` and
  `app/api/v1/endpoints/users.py`. The endpoints accept and return
  `AwareDatetime` instances serialized with the `Z` suffix per the
  UTC standard.
- [X] T036 [US1] Add logging for every US-1 operation: an
  `audit_events` row with `event_type` in
  `{user.registered, user.updated, user.profile_history_appended}`
  is produced by the service layer (the repository adapter writes
  the row, the service calls it).
- [X] T037 [US1] Run the US-1 smoke test from `quickstart.md` § 4.1
  to confirm the user can register and read their profile
  end-to-end.

**Checkpoint**: User Story 1 is fully functional and testable
independently. This is the MVP: a registered user exists, the
profile is mutable, and the audit log captures the events.

---

## Phase 4: User Story 2 — Configure a Learning Schedule with Modality (Priority: P1)

**Goal**: A registered user can create, list, and update schedules
with start/end times, a recurrence pattern, a modality (in-person or
virtual), and modality-specific information. Virtual classes
reference a registered platform with a URL; in-person classes
reference a location.

**Independent Test**: Register a user, register a virtual platform,
create a virtual schedule referencing the platform, list the user's
schedules, fetch one, and update its end time.

- [X] T038 [P] [US2] Add integration tests in
  `tests/api/test_schedules.py` and `tests/api/test_platforms.py`
  covering the US-2 acceptance scenarios: virtual modality requires
  a platform and URL; in-person modality requires a location;
  end time MUST be strictly after start time; previously registered
  platforms are reusable; editing a schedule does not retroactively
  rewrite historical sessions.
- [X] T039 [P] [US2] Implement the domain entities in
  `app/core/entities/external_learning_platform.py` and
  `app/core/entities/schedule.py` with the fields from
  `data-model.md`. Modality is an enum (`in_person`, `virtual`);
  exactly one of `platform_id` or `location` MUST be set per the
  modality.
- [X] T040 [US2] Implement the `platform_service` and
  `schedule_service` in `app/services/platform_service.py` and
  `app/services/schedule_service.py`. The schedule service uses
  the `clock` port and the `week_boundary_strategy` to expand
  schedules into sessions (the expansion is recomputed on every
  change; see `data-model.md`).
- [X] T041 [US2] Implement the platform and schedule endpoints in
  `app/api/v1/endpoints/platforms.py` and
  `app/api/v1/endpoints/schedules.py`. The endpoints enforce the
  per-modality validation rules and the strict end-after-start
  rule from FR-010/FR-011.
- [X] T042 [US2] Add logging for every US-2 operation: an
  `audit_events` row with `event_type` in
  `{platform.registered, platform.removed, schedule.created,
  schedule.updated, schedule.deleted, sessions.expanded}`.
- [X] T043 [US2] Run the US-2 smoke test from `quickstart.md` § 4.2
  and § 4.3 end-to-end.

**Checkpoint**: User Story 2 is fully functional and testable
independently. A user can manage platforms and schedules; the
expansion into concrete sessions is deterministic in the user's
time zone.

---

## Phase 5: User Story 3 — Receive a Learning Reminder (Priority: P2)

**Goal**: Five minutes before the scheduled start time of each
session, the system sends an email notification to the user with the
session information and the modality-specific content.

**Independent Test**: Schedule a session five or more minutes in the
future, advance the system clock to five minutes before start, and
confirm that a single email is produced with the correct content
(for virtual: the platform URL; for in-person: the location). The
reminder is delivered in the user's time zone.

- [X] T044 [P] [US3] Add integration tests in
  `tests/integration/test_reminder_dispatch.py` and VCR-recorded
  tests in `tests/services/test_reminder_service.py` (cassette
  `tests/vcr_cassettes/reminder_dispatch.yaml`). Tests cover:
  reminder produced at `scheduled_start_at - 5 minutes`; reminder
  content includes the modality-specific field; no email is
  produced when the feature is disabled in `feature_availability`;
  reminder failures are logged but do not surface to the user; a
  user who updates the schedule does not receive a reminder for
  the old session.
- [X] T045 [US3] Implement the `reminder_service` in
  `app/services/reminder_service.py`. The service reads the
  `feature_availability` for the `reminders` feature, computes
  the reminder instant (`scheduled_start_at - 5 minutes`) in the
  user's tz, and dispatches the email via the `email_sender` port.
- [X] T046 [US3] Implement the asynchronous worker that runs the
  reminder service on a schedule (the worker is a forward concern
  per `plan.md` § Open Decisions; for the initial release, the
  worker is a single async loop driven by an in-process scheduler,
  behind a `scheduler` port). The worker is started by the
  application's lifespan handler.
- [X] T047 [US3] Add logging for every US-3 operation: an
  `audit_events` row with `event_type` in
  `{reminder.scheduled, reminder.dispatched, reminder.suppressed,
  reminder.failed}`. The user's time zone is recorded on every
  row.
- [X] T048 [US3] Run the US-3 smoke test from `quickstart.md` § 4
  with a manually advanced clock and confirm the email is
  produced.

**Checkpoint**: User Story 3 is fully functional and testable
independently. Reminders are produced in the user's time zone and
respect the configurable feature gate.

---

## Phase 6: User Story 4 — Document a Daily Learning Record (Priority: P1)

**Goal**: A user can submit a daily summary for a session. The
summary is persisted as immutable history. The on-time/late status
is derived from the user's time zone and the 30-minute window.
Pre-start submissions are accepted and flagged.

**Independent Test**: Submit a summary within the 30-minute window
and verify `on_time`; submit another summary outside the window and
verify `late`; attempt to submit a second summary for the same
session and verify it is rejected; attempt to submit an empty
summary and verify it is rejected; submit a summary before the
session start and verify the `submitted_before_session_start`
flag is set.

- [X] T049 [P] [US4] Add integration tests in
  `tests/api/test_summaries.py` and
  `tests/integration/test_summary_repository.py` covering the
  US-4 acceptance scenarios, including: on-time vs late derivation
  at the 30-minute boundary; pre-start flagging; duplicate
  rejection; empty-content rejection; the session is never silently
  reclassified as missed when a late submission arrives.
- [X] T050 [US4] Implement the `daily_summary` domain entity in
  `app/core/entities/daily_summary.py` with `content`,
  `submitted_at` (timezone-aware UTC), `submission_status` (enum
  `on_time`, `late`), `submitted_before_session_start` (bool),
  `session_id`, `owner_user_id`, `content_version`. The entity is
  append-only (FR-024, FR-024a, A-2).
- [X] T051 [US4] Implement the `submission_status_strategy` in
  `app/core/strategies/submission_status_strategy.py`. The
  strategy uses the user's tz to evaluate the 30-minute window
  after `scheduled_end_at` and returns `on_time` or `late`. The
  strategy uses `app/core/time/utc.py` and NEVER uses the host's
  local time.
- [X] T052 [US4] Implement the `summary_service` in
  `app/services/summary_service.py` exposing `submit`,
  `get_by_id`, and `list_in_range`. The service enforces immutability
  (no updates, no deletes), empty-content rejection, duplicate
  rejection per `session_id`, and computes the status at insert
  time.
- [X] T053 [US4] Implement the summary endpoint in
  `app/api/v1/endpoints/summaries.py`. The endpoint accepts
  `content` (non-empty), persists the summary, and returns the
  document with the derived status and the
  `submitted_before_session_start` flag.
- [X] T054 [US4] Add logging for every US-4 operation: an
  `audit_events` row with `event_type` in
  `{summary.submitted, summary.rejected_duplicate,
  summary.rejected_empty, summary.rejected_invalid_timestamp}`
  including the session ID, the submission timestamp, the
  derived status, the user's time zone, and the inputs used to
  compute the status (per FR-085).
- [X] T055 [US4] Run the US-4 smoke test from `quickstart.md` § 4.5
  and verify the immutability invariant and the on-time / late
  derivation in two distinct time zones.

**Checkpoint**: User Story 4 is fully functional and testable
independently. Daily summaries are immutable, the on-time/late
status is computed in the user's time zone, and the pre-start
submission flag is honored.

---

## Phase 7: User Story 12 — Operate the Two-Model Content Generation and Evaluation Workflow (Priority: P1 — Cross-cutting)

**Goal**: Implement the generation/evaluation workflow that every
content-producing story (US-5, US-6, US-7, US-9, US-11) depends on.
Generation and evaluation are separate, non-shared-prompt models. A
bounded corrective loop absorbs both validation rejections and
transient AI provider failures. Unapproved material is never
delivered.

**Independent Test**: Submit a generation request for a known user
with a known history; verify that the generation record exists, the
evaluation record exists, the verdict is `approved` or `rejected`,
and that an unapproved material is never surfaced. Then force a
rejection and verify the corrective loop produces a revised
generation; force a transient AI provider failure and verify the
loop absorbs it within the same bound.

- [X] T056 [P] [US12] Add integration tests in
  `tests/services/test_corrective_loop.py` and
  `tests/integration/test_content_workflow.py` covering: the
  corrective loop terminates within the configured bound;
  unapproved material is never delivered; transient provider
  failures are absorbed within the same bound; a bound-exhausted
  failure is logged with diagnostic detail; the evaluation
  verdict is auditable end-to-end.
- [X] T057 [US12] Implement the `content_generation` and
  `content_evaluation` domain entities in
  `app/core/entities/content_generation.py` and
  `app/core/entities/content_evaluation.py` per
  `data-model.md`. The `content_evaluation` carries a structured
  `criterion_assessments` object (vocabulary, grammar, sentence
  length, reading demands, writing demands, relevance), a
  `verdict` enum (`approved`, `rejected`), a `rationale`, and an
  `attempt_number`.
- [X] T058 [US12] Implement the `corrective_loop` in
  `app/services/content/corrective_loop.py`. The service enforces
  the bound (configurable per environment, default per A-10),
  records each attempt on `content_evaluations`, and returns
  either the approved material or a bound-exhausted failure. The
  loop is implemented with LangGraph (`research.md` § 4) and
  uses the `content_generator`, `content_evaluator`, and `clock`
  ports.
- [X] T059 [US12] Implement the `content_workflow` service in
  `app/services/content/content_workflow.py` that orchestrates a
  generation request: persist the `content_generation`, call the
  `corrective_loop`, and persist the `content_evaluation` rows
  with the right `attempt_number`. The service emits the
  `audit_events` row required by FR-086.
- [X] T060 [US12] Add logging for every US-12 operation: an
  `audit_events` row with `event_type` in
  `{content.generated, content.evaluated, content.approved,
  content.rejected, content.bound_exhausted}` and the
  criterion-level assessment.
- [X] T061 [P] [US12] Add an integration test in
  `tests/integration/test_content_workflow.py` that asserts the
  FR-046 contract: once a `daily_material` (or `weekly_material`,
  or `monthly_material`) is approved and persisted, repeated
  fetches of the same material by the same user MUST return the
  same approved `content_evaluation` row and MUST NOT trigger a
  new corrective-loop run. The test seeds an approved material,
  records the `_id` of the linked `content_evaluation`, then
  issues at least two concurrent fetches and asserts that (a) the
  responses carry the same `evaluation_id`, (b) the count of
  `content_evaluations` rows for that material is unchanged, and
  (c) no new `audit_events` row of type `content.evaluated` or
  `content.generated` is recorded. The same property is asserted
  for `weekly_material` and `monthly_material` to confirm the
  guarantee is per-material and not per-period (a daily material
  and a weekly material are independent units of delivery and
  are each delivered exactly once).


**Checkpoint**: The two-model content workflow is operational.
Every content-producing user story can now build on top of it.

---

## Phase 8: User Story 5 — Generate and Receive Daily Reading and Writing Practice (Priority: P1)

**Goal**: After a daily summary is persisted, the system generates
reading and writing exercises grounded in the summary and the user's
documented history, at a difficulty appropriate to the user's CEFR
level. The material is delivered only after the
`content_workflow` approves it (US-12).

**Independent Test**: Submit a daily summary; poll the daily-material
endpoint and verify the approved material arrives; verify the
material references relevant prior history; verify an unapproved
material is never returned.

- [X] T062 [P] [US5] Add integration tests in
  `tests/api/test_daily_materials.py` and
  `tests/integration/test_daily_material_pipeline.py` covering
  the US-5 acceptance scenarios: the material references the
  summary and the user's history; the material is tagged with
  the user's CEFR level; the material is delivered only when
  the evaluation verdict is `approved`; a corrective-loop
  rejection does not surface unapproved material.
- [X] T063 [P] [US5] Implement the `daily_material` domain entity
  in `app/core/entities/daily_material.py` per `data-model.md`.
- [X] T064 [US5] Implement the `daily_material_service` in
  `app/services/daily_material_service.py` that wires the
  `summary_service` (US-4) to the `content_workflow` (US-12) and
  persists the approved material. The service uses the
  `content_workflow` to ensure the approval gate is never
  bypassed.
- [X] T065 [US5] Implement the daily-material endpoints in
  `app/api/v1/endpoints/daily_materials.py` and add a
  `GET /users/me/sessions/{session_id}/summary/material` route
  to the summary endpoint.
- [X] T066 [US5] Add logging for every US-5 operation: an
  `audit_events` row with `event_type` in
  `{daily_material.requested, daily_material.approved,
  daily_material.delivered, daily_material.bypassed_attempt}`
  (the last row is emitted and alerts if it is ever non-empty).
- [X] T067 [US5] Run the US-5 smoke test from `quickstart.md` § 4.6
  and confirm the approved material is delivered.

**Checkpoint**: User Story 5 is fully functional and testable
independently. The user can read the daily material after
submitting a summary.

---

## Phase 9: User Story 6 — Review a Weekly Learning Summary (Priority: P2)

**Goal**: At the end of the week, the user can fetch a weekly
summary that consolidates on-time / late / missing counts, recorded
study time, consistency indicators, and the knowledge documented
during the week. The weekly material is generated and gated by
the same `content_workflow` (US-12).

**Independent Test**: Seed a known week with a mix of on-time,
late, and missing summaries; fetch the weekly summary; verify
the counts and the weekly material is approved and surfaced.

- [X] T068 [P] [US6] Add integration tests in
  `tests/api/test_weekly_summaries.py` and
  `tests/integration/test_weekly_rollup.py` covering the US-6
  acceptance scenarios: weekly boundary is Monday 00:00 → next
  Monday 00:00 in the user's tz; on-time/late/missing counts
  reflect the actual mix; weekly material is gated by US-12; a
  week with no submissions still returns a summary.
- [X] T069 [P] [US6] Implement the `weekly_summary` and
  `weekly_material` domain entities in
  `app/core/entities/weekly_summary.py` and
  `app/core/entities/weekly_material.py` per `data-model.md`.
- [X] T070 [US6] Implement the `weekly_rollup` service in
  `app/services/weekly_rollup.py` that consumes the
  `summary_repository` and produces a `WeeklySummary` for the
  week containing the trigger date. The rollup is computed in
  the user's time zone using the `week_boundary_strategy`.
- [X] T071 [US6] Implement the weekly-summary and weekly-material
  endpoints in `app/api/v1/endpoints/weekly_summaries.py`. The
  endpoints accept a date range (or a single Monday) and return
  the corresponding period summaries and materials.
- [X] T072 [US6] Add logging for every US-6 operation: an
  `audit_events` row with `event_type` in
  `{weekly_summary.requested, weekly_summary.computed,
  weekly_material.approved, weekly_material.delivered}`.
- [X] T073 [US6] Run a manual rollup for a seeded week and confirm
  the counts and the weekly material.

**Checkpoint**: User Story 6 is fully functional and testable
independently.

---

## Phase 10: User Story 7 — Review a Monthly Learning Summary (Priority: P3)

**Goal**: At the end of the month, the user can fetch a monthly
summary that consolidates weekly activity and the cumulative
material, with the same approval gate.

**Independent Test**: Seed a known month; fetch the monthly summary;
verify the monthly counts and the monthly material is approved and
surfaced.

- [X] T074 [P] [US7] Add integration tests in
  `tests/api/test_monthly_summaries.py` and
  `tests/integration/test_monthly_rollup.py` covering the US-7
  acceptance scenarios: monthly boundary is the calendar month in
  the user's tz; monthly material is gated by US-12; a month
  with no submissions still returns a summary.
- [X] T075 [P] [US7] Implement the `monthly_summary` and
  `monthly_material` domain entities in
  `app/core/entities/monthly_summary.py` and
  `app/core/entities/monthly_material.py` per `data-model.md`.
- [X] T076 [US7] Implement the `monthly_rollup` service in
  `app/services/monthly_rollup.py` that consumes the
  `weekly_summary_repository` and produces a `MonthlySummary`
  for the month containing the trigger date.
- [X] T077 [US7] Implement the monthly-summary and monthly-material
  endpoints in `app/api/v1/endpoints/monthly_summaries.py`.
- [X] T078 [US7] Add logging for every US-7 operation: an
  `audit_events` row with `event_type` in
  `{monthly_summary.requested, monthly_summary.computed,
  monthly_material.approved, monthly_material.delivered}`.
- [X] T079 [US7] Run a manual rollup for a seeded month and confirm
  the counts and the monthly material.

**Checkpoint**: User Story 7 is fully functional and testable
independently.

---

## Phase 11: User Story 8 — Retrieve Historical Learning Records and Materials (Priority: P2)

**Goal**: The user can browse their history by day, week, or month
and see the corresponding summaries and materials. Late submissions
remain visible with their `late` status. The relationship between
the recorded activity and its material is preserved.

**Independent Test**: Seed a known history with a mix of on-time,
late, and missing entries plus a daily material; query by day,
week, and month; verify each result.

- [X] T080 [P] [US8] Add integration tests in
  `tests/api/test_history.py` covering the US-8 acceptance
  scenarios: day / week / month retrieval; late submissions are
  visible with their `late` status; materials returned for a
  period are the materials that were generated for that period,
  not regenerated on demand; an empty period returns a clear "no
  records" message.
- [X] T081 [P] [US8] Implement the `history_service` in
  `app/services/history_service.py` that composes
  `summary_service`, `daily_material_service`, `weekly_*` and
  `monthly_*` services. The service preserves the period
  boundaries and returns late submissions in the result set.
- [X] T082 [US8] Implement the history endpoints in
  `app/api/v1/endpoints/history.py` per
  `contracts/README.md` (day, week, month, and range variants).
- [X] T083 [US8] Add logging for every US-8 operation: an
  `audit_events` row with `event_type` in
  `{history.day_requested, history.week_requested,
  history.month_requested, history.range_requested}` including
  the requested range and the result counts.
- [X] T084 [US8] Run a manual history query for a seeded
  multi-period dataset and confirm the response shape.

**Checkpoint**: User Story 8 is fully functional and testable
independently.

---

## Phase 12: User Story 9 — Converse with the Personalized AI Learning Assistant (Priority: P2)

**Goal**: The user can open a thread, ask a question, and receive a
response adapted to their CEFR level, grounded in their documented
learning history, and addressed by their preferred name. The
assistant uses the `content_workflow` for any educational content
it generates (US-12) and uses RAG (with per-user isolation) to
retrieve relevant chunks from `summary_chunks`.

**Independent Test**: Open a thread; ask a known question; verify
the response references the user's history, is written at the
user's CEFR level, and addresses the user by their preferred name.
Verify a second user cannot access the thread.

- [X] T085 [P] [US9] Add integration tests in
  `tests/api/test_assistant.py` and
  `tests/integration/test_assistant_retrieval.py` covering the
  US-9 acceptance scenarios: response difficulty matches CEFR;
  response references the user's history; preferred name is used;
  non-text input is rejected with a clear error; cross-user
  access is rejected.
- [X] T086 [P] [US9] Implement the `assistant_thread` domain
  entity in `app/core/entities/assistant_thread.py` per
  `data-model.md`.
- [X] T087 [P] [US9] Implement the RAG pipeline: chunk the
  user's summaries on insert, embed, and index the chunks in
  `summary_chunks` (per the deferred chunking/embedding
  decisions; the initial release uses the in-process numpy
  adapter). The retrieval step filters by `owner_user_id` for
  per-user isolation.
- [X] T088 [US9] Implement the `assistant_service` in
  `app/services/assistant_service.py` that consumes the
  `user_service`, the `summary_service`, the RAG pipeline, the
  `content_workflow` (for any generated content), and the
  `content_generator` port (for the conversational reply).
- [X] T089 [US9] Implement the assistant endpoints in
  `app/api/v1/endpoints/assistant.py` per
  `contracts/README.md`. The endpoints reject non-text payloads
  with a `415 Unsupported Media Type`.
- [X] T090 [US9] Add logging for every US-9 operation: an
  `audit_events` row with `event_type` in
  `{assistant.thread_opened, assistant.message_appended,
  assistant.turn_completed, assistant.rejected_non_text,
  assistant.cross_user_access_denied}`.
- [X] T091 [US9] Run the US-9 smoke test from `quickstart.md` § 4.8
  and confirm the response references the user's history.

**Checkpoint**: User Story 9 is fully functional and testable
independently.

---

## Phase 13: User Story 10 — Review Reading, Writing, and Consistency Progress Indicators (Priority: P2)

**Goal**: The user can fetch a three-dimension progress report
(reading, writing, consistency) with the explicit activity-vs-
proficiency disclaimer.

**Independent Test**: Seed a known history; fetch `/users/me/
progress`; verify the three sections are populated independently
and the response carries the disclaimer.

- [X] T092 [P] [US10] Add integration tests in
  `tests/api/test_progress.py` covering the US-10 acceptance
  scenarios: three separate sections (reading, writing,
  consistency); disclaimers present; insufficient evidence is
  communicated; no field can be interpreted as a proficiency
  score.
- [X] T093 [US10] Implement the `progress_service` in
  `app/services/progress_service.py` that composes
  `summary_service`, `daily_material_service`, and the
  `recommendation_strategy` to compute the three-dimension
  report. The service is the only place that produces progress
  numbers; the API surface is a thin wrapper.
- [X] T094 [US10] Implement the progress endpoints in
  `app/api/v1/endpoints/progress.py` per
  `contracts/README.md` (`/users/me/progress` and
  `/users/me/progress/streaks`).
- [X] T095 [US10] Add logging for every US-10 operation: an
  `audit_events` row with `event_type` in
  `{progress.requested, streaks.requested}`.
- [X] T096 [US10] Run a manual progress fetch for a seeded user
  and confirm the response shape.

**Checkpoint**: User Story 10 is fully functional and testable
independently.

---

## Phase 14: User Story 11 — Receive Motivation, Recognition, and Progressive Challenges (Priority: P3)

**Goal**: The user receives recognitions (e.g., on-time streaks)
and progressive challenges. The challenges are CEFR + 1 bounded
and are produced through the same `content_workflow` (US-12).

**Independent Test**: Seed a user with a streak; fetch recognitions;
fetch challenges; start a challenge; verify the challenge
material is approved and surfaced.

- [X] T097 [P] [US11] Add integration tests in
  `tests/api/test_motivation.py` covering the US-11 acceptance
  scenarios: on-time streak recognition; the recommended
  challenge is at most CEFR + 1; the user at the highest CEFR
  level receives refinements within the same level; a user with
  no history receives a starting challenge at the declared CEFR
  level.
- [X] T098 [P] [US11] Implement the `recognitions` and
  `challenges` domain entities in
  `app/core/entities/recognition.py` and
  `app/core/entities/challenge.py`.
- [X] T099 [US11] Implement the `motivation_service` in
  `app/services/motivation_service.py` that uses
  `progress_service` to compute recognitions and
  `recommendation_strategy` (CEFR + 1) to compute the next
  challenge.
- [X] T100 [US11] Implement the motivation and challenge endpoints
  in `app/api/v1/endpoints/motivation.py` and
  `app/api/v1/endpoints/challenges.py` per
  `contracts/README.md`.
- [X] T101 [US11] Add logging for every US-11 operation: an
  `audit_events` row with `event_type` in
  `{recognition.computed, challenge.recommended,
  challenge.started, challenge.material_approved,
  challenge.material_delivered}`.
- [X] T102 [US11] Run a manual motivation fetch and a manual
  challenge-start for a seeded user.

**Checkpoint**: User Story 11 is fully functional and testable
independently.

---

## Phase 15: User Story 13 — Respect Configurable Feature Availability (Priority: P3 — Cross-cutting)

**Goal**: Selected features can be disabled through configuration.
A disabled feature returns a clear "not currently available"
message and the corresponding endpoint is gated at the API
boundary.

**Independent Test**: Disable the `reminders` feature in
configuration; confirm that scheduling a reminder produces no
email and the corresponding endpoint returns the documented "not
currently available" message.

- [X] T103 [P] [US13] Add integration tests in
  `tests/api/test_feature_availability.py` covering the US-13
  acceptance scenarios: a disabled feature returns a clear "not
  currently available" message; configuration changes take effect
  without re-login; the global on/off switch is honored.
- [X] T104 [P] [US13] Implement the `feature_availability`
  domain entity in `app/core/entities/feature_availability.py`
  per `data-model.md` (a single document with `_id` =
  feature name, `enabled` boolean).
- [X] T105 [US13] Implement the `feature_availability_service`
  in `app/services/feature_availability_service.py` and the
  API-layer dependency that consults it before each gated
  endpoint.
- [X] T106 [US13] Implement the system endpoints in
  `app/api/v1/endpoints/system.py` per `contracts/README.md`
  (`/system/features` and `/system/health`).
- [X] T107 [US13] Add logging for every US-13 operation: an
  `audit_events` row with `event_type` in
  `{feature_availability.disabled, feature_availability.enabled,
  feature_availability.request_rejected}`.
- [X] T108 [US13] Run the US-13 smoke test (toggle a feature off
  and confirm the response) and confirm the runtime image does
  not embed any feature-availability override.

**Checkpoint**: User Story 13 is fully functional and testable
independently. Per-user overrides remain a forward concern per
FR-081.

---

## Phase 16: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories. The
final acceptance gates from the user-supplied plan and the
constitution.

- [X] T109 [P] Add the `quickstart.md` end-to-end smoke test as a
  single executable script at
  `scripts/smoke_test.sh` so the entire user journey from §4 of
  `quickstart.md` can be replayed in CI.
- [X] T110 [P] Add the UTC standard validation suite as a single
  executable at `scripts/utc_standard_check.sh`: it runs the
  API fixtures from `quickstart.md` § 9.1, asserts the
  persistence invariants from § 9.2, asserts the static lint
  from § 9.3, and asserts the logging format from § 9.4.
- [X] T111 [P] Add the Docker image content validation at
  `scripts/image_content_check.sh`: it builds the `dev`, `test`,
  and `runtime` targets, asserts that the runtime image does
  not contain `tests/` or `requirements_test.txt`, and asserts
  that the runtime image emits a Z-suffixed UTC log line.
- [X] T112 [P] Add the LocalStack secret repeatability and
  missing-secret tests at
  `tests/integration/test_localstack_secrets.py`. The tests run
  `scripts/init-localstack.sh` twice and assert the secret
  list is identical; the tests also assert that a missing
  mandatory secret produces an explicit configuration error.
- [X] T113 [P] Add a security review pass per OWASP API Security
  Top 10: authentication and authorization (covered by US-1,
  US-9); object-level and property-level access control
  (covered by per-user filtering in every repository); input
  validation and payload limits (covered by the Pydantic
  `AwareDatetime` rejection and the `validation` task per
  endpoint); resource consumption limits (rate limiting is a
  forward concern); abuse of sensitive business workflows
  (covered by the corrective loop bound); SSRF prevention
  (the AI / email / platform URL adapters validate
  destinations); secure configuration and secret handling
  (covered by the `SecretProvider` port and the LocalStack
  configuration).
- [X] T114 [P] Add the dependency-evaluation document at
  `docs/dependency_evaluation.md` listing every dependency in
  `requirements.txt` and `requirements_test.txt` with its
  maintenance status, Python 3.14.8 compatibility, known
  vulnerabilities, transitive dependencies, license, and
  version pin. The document is updated on every dependency
  change.
- [X] T115 [P] Add the constitution compliance review
  documentation at `docs/constitution_compliance.md` mapping
  every principle in `.specify/memory/constitution.md` to
  the specific files and tests that verify compliance.
- [X] T116 Add `main.py` graceful shutdown that flushes
  pending reminder dispatches, finalizes any in-flight
  corrective loops, and closes the MongoDB client. The
  shutdown handler is covered by an integration test.
- [X] T117 [P] Add a single end-to-end test that runs the
  full user journey (registration → schedule → reminder →
  summary → daily material → weekly summary → assistant →
  progress) against the FastAPI TestClient with fakes for
  every external adapter. The test is the final integration
  gate before the release is tagged.
- [X] T118 Run `python -m unittest discover -s tests` and
  confirm zero failures. Run the smoke test, the UTC standard
  checks, the image content check, and the LocalStack secret
  tests. All must pass.

## Phase 16b: Real AI Provider for the Two-Model Workflow (T119)

**Goal**: replace the deterministic stub pair with two REAL models
served by Ollama (native API `POST /api/chat`), keeping the two roles
structurally independent and the approval gate intact.

- [X] T119 [Story] Add the AI provider error hierarchy
  (`app/core/ports/ai_errors.py`: `AIProviderError`,
  `TransientAIError`, `NonTransientAIError`) and re-export
  `TransientAIError` from the generator port so the existing
  imports keep working.
- [X] T120 [P] [Story] Add the Ollama client adapter
  (`app/adapters/external/ai/ollama_client.py`): `POST /api/chat`
  over `niquests` in synchronous mode inside `asyncio.to_thread`,
  with the transient/permanent error mapping, the truncated-answer
  refusal and the JSON extraction.
- [X] T121 [P] [Story] Add the wire schemas
  (`app/adapters/external/ai/ollama_schemas.py`): the material,
  conversational and evaluation envelopes plus the schema snippets
  embedded in each role's prompt.
- [X] T122 [P] [Story] Add the generation adapter
  (`app/adapters/external/ai/ollama_generator.py`): the native-English-
  teacher role, the CEFR calibration, the scope delimitation (no
  problem-solving, no code, no arithmetic, no deep reasoning) and the
  grounding of the documented history as untrusted data.
- [X] T123 [P] [Story] Add the evaluation adapter
  (`app/adapters/external/ai/ollama_evaluator.py`): the strict CEFR
  examiner role, the six criteria, and the FAIL-CLOSED verdict
  (approved only with all six criteria present and passing).
- [X] T124 [Story] Add the AI configuration
  (`AI_PROVIDER`, `AI_BASE_URL`, `AI_GENERATION_MODEL`,
  `AI_EVALUATION_MODEL`, the two token budgets, the request timeout
  and `keep_alive`) and the `AI_BASE_URL` passthrough in
  `compose.yaml` (the container reaches the host through
  `host.docker.internal`, never `127.0.0.1`).
- [X] T125 [Story] Wire the provider PAIR in the composition root
  (`main.py`): the test environment keeps the deterministic pair, the
  rest uses the Ollama pair, and the provider is primed at startup
  (fail fast outside development/test, contained locally).
- [X] T126 [Story] Give the assistant its own generation kind
  (`GenerationInputs.kind`): the conversational envelope with the
  `payload["reply"]` and the backward-compatible fallback.
- [X] T127 [Story] Make the corrective loop's bound cover the
  transient failures too (A-17: no separate transient-failure
  counter) and assert the new invariant in the tests.
- [X] T128 [Story] Add the adapter test suites with VCR cassettes
  (`tests/adapters/test_ollama_client.py`,
  `test_ollama_generator.py`, `test_ollama_evaluator.py`,
  `test_ollama_content_gate.py`): the HTTP contract, the error
  mapping, the role isolation, the fail-closed verdict and the
  content validation gate with the real models (a good B1 material
  approved; a programming lesson rejected and never delivered).
- [X] T129 [Story] Update the documentation: the dependency
  evaluation (the `niquests` row and the AI-provider authentication
  note), the constitution compliance review (the two-model row, the
  gate and the known pending items), the security review (the AI
  provider section) and this file's research decision.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion.
  **BLOCKS all user stories.**
- **User Stories (Phase 3–15)**: All depend on Foundational phase
  completion. US-1, US-2, US-4, US-5, US-12 are P1; US-3, US-6,
  US-8, US-9, US-10 are P2; US-7, US-11, US-13 are P3. US-12
  (two-model content workflow) is a P1 cross-cutting dependency
  for US-5, US-6, US-7, US-9, and US-11. The recommended
  implementation order is: US-1 → US-2 → US-4 → US-12 → US-5 →
  US-3 → US-6 → US-8 → US-9 → US-10 → US-7 → US-11 → US-13.
- **Polish (Phase 16)**: Depends on all user stories being
  complete.

### Within Each User Story

- Tests are written and FAIL before implementation (the
  user-supplied plan requires tests; see `plan.md` § 10).
- Domain entities before repositories.
- Repositories before services.
- Services before endpoints.
- Endpoints before integration tests.
- Logging (`audit_events`) is added in the same phase as the
  operation it audits.
- UTC compliance is verified in the same phase as the
  operation it constrains.

### Within Phase 2 (Foundational)

- T012 (UTC helpers) and T013 (logging) can run in parallel.
- T014 (ports) defines the contracts that the repositories
  (T019) and the strategies (T016) implement.
- T015 (config / secret provider) is independent of the
  ports.
- T017 (MongoDB client), T018 (mappers), and T019
  (repositories) form a chain: client → mappers →
  repositories. The mappers can be written before the
  repositories, in parallel with the client.
- T020 (in-process AI stubs) and T021 (email fakes) can run
  in parallel with the persistence chain.
- T022 (request models) and T023 (response models) and T024
  (error handlers) can run in parallel.
- T025 (router skeleton) depends on T022 / T023 / T024.
- T026 (import-direction lint) and T027 (no-implicit-local-
  time lint) are independent and can run as soon as the
  corresponding code exists.
- T028 (audit-event writer) is independent of the rest of
  Phase 2 except for the port defined in T014.
- T029 (test fixtures) depends on the persistence chain
  (T017–T019) and the config / secret provider (T015).

### Parallel Opportunities

- All Setup tasks marked `[P]` can run in parallel.
- All Foundational tasks marked `[P]` can run in parallel
  within Phase 2.
- Once Foundational phase completes, all user stories can
  start in parallel if team capacity allows.
- All tests for a user story marked `[P]` can run in parallel.
- Domain entities within a story marked `[P]` can run in
  parallel.

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational.
3. Complete Phase 3: User Story 1.
4. **STOP and VALIDATE**: test User Story 1 independently.
5. Deploy / demo if the registration and profile flow alone
   is the desired MVP.

### Incremental Delivery (recommended for this project)

1. Complete Setup + Foundational → foundation ready.
2. Add US-1 (register) → test independently.
3. Add US-2 (schedules) → test independently.
4. Add US-4 (daily summaries) → test independently.
5. Add US-12 (two-model workflow) → test independently.
6. Add US-5 (daily material) → test independently — **the
   minimum end-to-end learning loop is now demoable**.
7. Add US-3 (reminders), US-6 (weekly summary), US-8 (history),
   US-9 (assistant), US-10 (progress), US-7 (monthly summary),
   US-11 (motivation), US-13 (feature availability) in any
   order.
8. Run Phase 16 (polish and cross-cutting) before tagging the
   initial release.

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together.
2. Once Foundational is done:
   - Developer A: US-1 + US-2 + US-4 (the registration →
     schedule → summary chain).
   - Developer B: US-12 (two-model workflow, isolated behind
     a port).
   - Developer C: US-3 (reminders) + US-13 (feature
     availability, since it depends on the global config).
3. After US-12 is operational:
   - Developer A picks up US-5 + US-6 + US-7 (the
     summary → material → rollup chain).
   - Developer B picks up US-8 + US-9 + US-10 (history,
     assistant, progress).
   - Developer C picks up US-11 (motivation, which uses
     progress).
4. Stories complete and integrate independently; the smoke
   test in `quickstart.md` § 4 is the final integration
   gate.

---

## Notes

- `[P]` tasks = different files, no dependencies on incomplete
  tasks.
- `[Story]` label maps each task to the user story it serves
  for traceability.
- Every user story is independently completable and testable.
- The constitution's compliance gates are reflected in
  dedicated tasks (UTC standard = T012, T013, T027;
  import-direction = T026; logging format = T013; audit log =
  T028 plus per-story `audit_events` rows; two-model workflow
  = US-12).
- The thirteen open decisions listed in `plan.md` and
  `research.md` remain forward concerns; the implementation
  uses the deferred-decision placeholders documented there
  until each is approved.
- Every code change is committed after the corresponding task
  or logical group; the build is considered green when
  `python -m unittest discover -s tests` reports zero failures
  and the smoke / UTC / image-content / LocalStack checks all
  pass.
