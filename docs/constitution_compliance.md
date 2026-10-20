# Constitution Compliance Review

T115 — maps every constitution principle (`.specify/memory/constitution.md`
v1.0.0) to the specific files and tests that verify compliance.

## Core principles

| Principle | Implementation | Verifying tests |
|---|---|---|
| **I. CEFR-Aligned Content Difficulty** | `app/adapters/external/ai/ollama_generator.py` (level-calibrated generation prompt), `app/adapters/external/ai/ollama_evaluator.py` (CEFR examiner, six criteria), `app/adapters/external/ai/deterministic_ai.py` (offline rubric), `app/core/strategies/recommendation_strategy.py` (CEFR+1), `app/services/content/content_workflow.py` (approval gate) | `tests/services/test_corrective_loop.py`, `tests/api/test_motivation.py`, `tests/api/test_daily_materials.py`, `tests/adapters/test_ollama_content_gate.py` (real models, cassette replay) |
| **II. Two-Model Generation/Evaluation** | separate ports `app/core/ports/content_generator.py` / `content_evaluator.py`; separate adapters (`app/adapters/external/ai/ollama_generator.py`, `app/adapters/external/ai/ollama_evaluator.py` — distinct system prompts, distinct clients, distinct models, no shared state); bounded loop `app/services/content/corrective_loop.py` (LangGraph) | `tests/services/test_corrective_loop.py` (rejection→revision, bound exhaustion, transient absorption), `tests/adapters/test_ollama_evaluator.py` (role isolation, fail-closed verdict), `tests/adapters/test_ollama_content_gate.py` (gate with real models), `tests/integration/test_content_workflow.py` (persistence + FR-046) |
| **III. Personalization from Documented History** | `app/services/rag_service.py` (chunk+embed+index on summary insert, retrieval filters `owner_user_id`); `app/services/daily_material_service.py` (history slice in generation inputs) | `tests/integration/test_assistant_retrieval.py` (per-user isolation), `tests/api/test_daily_materials.py` ("documented" grounding) |
| **IV. Reliable Learning Records / Submission Integrity** | append-only `daily_summaries` (unique `session_id` insert-only, `app/adapters/persistence/mongodb/repositories/summary_repository.py`); statuses computed at insert and immutable; late never reclassified | `tests/api/test_summaries.py`, `tests/integration/test_summary_repository.py` |
| **V. Activity Metrics ≠ Proficiency Evidence** | `app/services/progress_service.py` (three dimensions + disclaimers; no proficiency score fields) | `tests/api/test_progress.py` (disclaimer presence, `PROFICIENCY_SUSPECTS` scan, insufficient-evidence message) |
| **VI. Time-Zone Consistent Scheduling** | user tz applied at boundaries via `app/core/time/wall_clock.py`, strategies `app/core/strategies/{submission_status,week_boundary,month_boundary}_strategy.py`; sessions expanded in the user's tz; reminder rendered in user tz | `tests/core/test_strategies.py` (3 tzs incl. DST), `tests/api/test_summaries.py` (3 tzs), `tests/integration/test_weekly_rollup.py` |
| **VII. Progressive, Evidence-Based Difficulty** | `RecommendationStrategy.recommend` (evidence-gated one-level progression) + CEFR+1 bound enforced again at challenge start (`app/services/motivation_service.py`) | `tests/core/test_strategies.py`, `tests/api/test_motivation.py` |
| **VIII. Motivation & Positive Reinforcement** | `app/services/motivation_service.py` (recognitions + appropriate challenge descriptions) | `tests/api/test_motivation.py` |
| **IX. Separation of Responsibilities** | ports in `app/core/ports/`, adapters in `app/adapters/`, services in `app/services/`; no service→adapter imports | `tests/core/test_import_direction.py` (enforced in the suite) |
| **X. Observability & Failure Containment** | `app/utils/logging.py` (`report_error`/`report_info`, UTC asctime, secret redaction); `audit_events` on every privileged operation (FR-084–86); bounded `CorrectiveLoop`; contained reminder/email failures | `tests/core/test_utc_standard.py` + `tests/core/test_logging_format.py`, reminder containment test (`tests/services/test_reminder_service.py`), content bound-exhaustion tests |

## Non-functional standards

| Standard | Where enforced |
|---|---|
| Reliability | corrective-loop bound + transient absorption (`corrective_loop.py`); contained reminder failures; DB connectivity raises on startup (`client.py`) |
| Data Integrity | unique indexes (`client.py::_ensure_indexes`); immutability of summaries & materials (repositories); `version` bumps |
| Security & Privacy | `Authenticator` port + `app/adapters/external/auth/token_authenticator.py`; ownership checks (`app/api/v1/dependencies/auth.py`); per-user filters (every repo); secret redaction in logs; no real credentials committed (dummy- prefixed only) |
| Scalability | single-document Mongo, per-collection owner indexes, port/adapters layering allows scaling out without rewrites |
| Maintainability | one module responsibility per file; static import-direction lint; typed pydantic models |
| Content Quality | the evaluation gate (constitution principle II) |

## Compliance gates (workflow)

| Gate | Demonstrated by |
|---|---|
| Principle Compliance Review | this document + `tests/core/test_import_direction.py` |
| Content Validation Gate | corrective-loop tests (failing evaluation blocks delivery; bounded retries terminate) + the gate with the real models: `tests/adapters/test_ollama_content_gate.py` (a good B1 material is approved; a programming lesson is rejected on 4 of 6 criteria and never delivered) |
| Submission-Status Gate | `tests/api/test_summaries.py` (user tz + 30-minute window), `tests/core/test_strategies.py` |
| Time-Zone Gate | strategy + API tests in ≥ 3 time zones, DST-crossing week |
| Activity-vs-Proficiency Gate | `tests/api/test_progress.py::test_no_field_is_a_proficiency_score` |
| Data Integrity Gate | late submissions retained with status (repo + API + history tests) |
| Security Gate | cross-user isolation tests (assistant threads, repositories), duplicate/ownership conflicts |
| Observability Gate | audit-event assertions in `tests/integration/test_end_to_end.py` |

## UTC Mandatory Standard

| Rule | Enforcement | Test |
|---|---|---|
| 1 Storage (BSON Date, UTC) | `app/adapters/persistence/mongodb/mappers.py` | `tests/integration/test_summary_repository.py::test_utc_round_trip`, `test_user_repository.py::test_owner_user_id_scope_and_utc_invariant` |
| 2 Application logic | `app/core/time/utc.py` helpers | `tests/core/test_time_helpers.py` |
| 3 API `Z` suffix | `AwareDatetime` serializer (`when_used="json"`) | `tests/core/test_time_helpers.py`, `tests/api/test_requests_utc.py` |
| 4 Input validation | request-model validators + `app/api/v1/error_handlers.py` | `tests/api/test_requests_utc.py` (naive → invalid_timestamp → 400) |
| 5 External integrations | adapter boundaries (`secret_provider`, `localstack_email_sender`) | `tests/services/test_reminder_service.py` |
| 6 Logging UTC | `UTCFormatter` | `tests/core/test_logging_format.py`, image check |
| 7 Testing | this table | `tests/core/test_utc_standard.py` |
| 8 Consistency | `tests/core/test_utc_standard.py` static lint (forbids `datetime.now()`, `pytz`, non-UTC `astimezone` outside `app/core/time`/`app/core/strategies`) | the lint itself |
## Known pending items (documented, not implemented)

- **Real embeddings**: `DeterministicEmbeddingProvider` is a hash, so the
  assistant's RAG orders retrieved chunks arbitrarily. The generation and
  evaluation models are real, but the embedding provider is not. The
  `EmbeddingProvider` port already exists
  (`app/core/ports/embedding_provider.py`), so a real embedding adapter
  drops in behind the same interface without touching the services.
- **Chunking, retrieval ranking and context limits**: still open
  decisions (`research.md § 4`); the current retrieval is top-k by
  cosine similarity over hash vectors.
- **AI provider concurrency limit**: the provider adapter is concurrent
  across calls (`asyncio.to_thread` around a synchronous client), but
  there is no dedicated pool or rate limiter against the provider yet.
