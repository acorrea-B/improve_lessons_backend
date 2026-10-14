# Data Model: Improve Lessons Backend

**Phase**: 1 — Concrete schema derived from `specs/001-improve-lessons-backend/spec.md`
**Date**: 2026-10-13
**Persistence**: MongoDB (single source of truth), accessed through
`app/adapters/persistence/mongodb/`

This document defines the data model for the initial release. Every entity
maps to a MongoDB collection. The collection names, index definitions, and
the choice of `_id` strategy are deferred to `tasks.md` (open decision
"Exact MongoDB collections and indexes"). The shape of the documents is
fixed now so that downstream planning and contract generation are unblocked.

## Conventions

- **Identifiers**: every document uses a stable, opaque `_id` (UUIDv4) and a
  monotonically increasing `created_at` timestamp in UTC.
- **Ownership**: every document has an `owner_user_id` field that scopes
  reads and writes at the persistence layer.
- **Immutability**: the `daily_summaries` collection is append-only. Once a
  document is inserted, it is never updated or deleted (see
  `plan.md` §3 Data Integrity and FR-024a).
- **Timestamps**: every persisted timestamp is a timezone-aware UTC
  `datetime` stored as MongoDB BSON `Date` (which is UTC by definition).
  The application never persists a naive datetime and never persists a
  timestamp as a string. The only string-typed date/time fields are
  local wall-clock fields (e.g., `start_time`, `end_time` on schedules)
  which are stored as `HH:MM` strings and never converted to instants
  without a time zone.
- **API serialization**: timestamps leave the API as ISO 8601 strings
  with the `Z` suffix (e.g., `2026-10-13T14:30:00Z`). The Pydantic
  `AwareDatetime` annotation is bound to UTC and serializes to the
  `Z` suffix; explicit offsets such as `+00:00` are not emitted in
  responses. See "Time-zone handling" below.
- **Versioning**: every mutable document includes a `version` integer that
  increments on each write. Daily summaries and historical material records
  also include a `content_version` for the embedded reference, so that
  derived chunks can be invalidated when the source content changes.
- **Audit fields**: every document includes `created_at`, `updated_at`
  (where mutable), and the actor that performed the write
  (`created_by_user_id`, `last_modified_by_user_id`).

## Time-zone handling

The data model enforces the "Date and Time Handling — Mandatory UTC
Standard" defined in `plan.md` § Mandatory Standards.

- **Storage rule**: every persisted datetime is a timezone-aware UTC
  `datetime`. Naive datetimes are forbidden at the persistence boundary;
  the MongoDB adapter raises on a naive value before any insert or
  update. The only string-typed date/time fields are local wall-clock
  values that are NOT instants (see Conventions above).
- **Application rule**: all internal date/time calculations operate on
  timezone-aware UTC datetimes. The user's time zone is stored on the
  user document and is used to convert between UTC and the user's local
  wall clock at the application boundary (on-time/late derivation,
  weekly/monthly period boundaries, reminder scheduling). The user's
  time zone is NEVER used to persist an instant.
- **API rule**: API responses emit timestamps as `2026-10-13T14:30:00Z`
  (ISO 8601 with the `Z` suffix). API requests accept timestamps with
  explicit offsets; the request model normalizes them to UTC and rejects
  naive timestamps with a `400 Bad Request`. Local wall-clock fields
  (e.g., `start_time: "07:00"`) are accepted as `HH:MM` strings and are
  NOT treated as instants.
- **External integrations rule**: any datetime received from an
  external service is normalized to UTC at the adapter boundary.
- **Logging rule**: log timestamps are emitted in UTC with the `Z`
  suffix, regardless of the host's local time zone.

A shared `app/core/time/` module owns every helper used to satisfy
these rules (`now_utc`, `parse_iso_to_utc`, `to_utc_instant`,
`require_aware_utc`, `AwareDatetime`-compatible Pydantic type). No
other module is allowed to call `datetime.now()` without a `tz`
argument or to import `pytz`; a static test enforces this.

## Collections

### `users`

The registered learner. Created at registration; mutable thereafter for
profile fields; never deleted in this release (per FR-008a).

| Field | Type | Required | Notes |
|---|---|---|---|
| `_id` | UUID | yes | stable identifier |
| `name` | string | yes | legal name |
| `preferred_name` | string | no | used by the AI assistant (FR-062) |
| `email` | string | yes | unique, lowercased, RFC-5322 validated |
| `cefr_level` | enum | yes | one of `A1`, `A2`, `B1`, `B2`, `C1`, `C2` |
| `time_zone` | string | yes | IANA tz identifier (e.g., `America/Bogota`) |
| `created_at` | datetime | yes | UTC |
| `updated_at` | datetime | yes | UTC |
| `profile_history` | array of objects | no | append-only log of profile changes |
| `version` | int | yes | increments on every write |

**Validation rules**:
- `email` MUST be unique (case-insensitive).
- `cefr_level` MUST be one of the six allowed values.
- `time_zone` MUST be a valid IANA tz identifier; validated at write time
  by the adapter using `zoneinfo`.

**Relationships**:
- One user owns many `external_learning_platforms`.
- One user owns many `schedules`.
- One user owns many `daily_summaries`, `daily_materials`, `weekly_*`,
  `monthly_*`, `assistant_threads`, `feature_availability_overrides` (future).

### `users_profile_history`

Append-only log of changes to a user document. Each entry records the
previous and the new value for any changed field, the change timestamp, and
the user that performed the change (which is always the user themselves in
this release).

| Field | Type | Notes |
|---|---|---|
| `_id` | UUID | |
| `user_id` | UUID | FK to `users` |
| `changed_fields` | object | previous and new value per field |
| `changed_at` | datetime | UTC |
| `version` | int | |

### `external_learning_platforms`

A name/URL pair registered by a user for virtual-modality sessions
(FR-012).

| Field | Type | Required | Notes |
|---|---|---|---|
| `_id` | UUID | | |
| `owner_user_id` | UUID | yes | FK to `users` |
| `name` | string | yes | non-empty |
| `url` | string | yes | stored as provided; reachability not validated (A-5) |
| `created_at` | datetime | yes | UTC |
| `version` | int | | |

**Relationships**:
- One user owns many platforms.
- A platform is referenced by many `schedules`.

### `schedules`

A user's recurring learning configuration (FR-009 onward). Expands into
concrete `sessions` at the application layer; the expansion is recomputed
on every change.

| Field | Type | Required | Notes |
|---|---|---|---|
| `_id` | UUID | | |
| `owner_user_id` | UUID | yes | |
| `start_time` | string | yes | local HH:MM, evaluated in the user's tz |
| `end_time` | string | yes | local HH:MM, must be strictly after `start_time` (FR-010) |
| `recurrence` | enum | yes | one of `daily`, `every_other_day` (extensible) |
| `modality` | enum | yes | `in_person` or `virtual` |
| `platform_id` | UUID | conditional | required when `modality = virtual`; FK to `external_learning_platforms` |
| `location` | string | conditional | required when `modality = in_person` (FR-011) |
| `created_at` | datetime | yes | |
| `updated_at` | datetime | yes | |
| `version` | int | | |

**Validation rules**:
- Exactly one of `platform_id` or `location` MUST be set, in line with
  `modality`.
- A schedule that has produced sessions is not silently rewritten on edit
  (FR-014); edits apply to future sessions.

**Relationships**:
- One schedule expands into many `sessions`.

### `sessions`

A concrete planned learning event produced by expanding a `schedules` entry
(FR-013). Sessions are deterministic given the schedule and the user's tz.

| Field | Type | Required | Notes |
|---|---|---|---|
| `_id` | UUID | | |
| `owner_user_id` | UUID | yes | |
| `schedule_id` | UUID | yes | FK to `schedules` |
| `scheduled_start_at` | datetime | yes | UTC; the wall-clock instant in the user's tz |
| `scheduled_end_at` | datetime | yes | UTC; strictly after `scheduled_start_at` |
| `modality` | enum | yes | denormalized from the schedule |
| `platform_id` | UUID | conditional | denormalized |
| `platform_url` | string | conditional | denormalized; used in reminder emails |
| `location` | string | conditional | denormalized |
| `reminder_sent_at` | datetime | no | set when the reminder job completes |
| `created_at` | datetime | yes | |

**State transitions**:
- `planned` → `reminded` when FR-016's reminder email is produced.
- `planned` (or `reminded`) → `summarized` when a `daily_summary` is
  persisted.
- Sessions without a summary by the end of the user's day remain
  `planned`/`reminded`; they are counted as `missing` in weekly/monthly
  rollups (FR-027).

**Relationships**:
- One session has zero or one `daily_summary`.
- One session has zero or one `daily_material`.

### `daily_summaries`

The user's written record of what they learned for a given session.
**Append-only** (FR-024, FR-024a, A-2).

| Field | Type | Required | Notes |
|---|---|---|---|
| `_id` | UUID | | |
| `owner_user_id` | UUID | yes | |
| `session_id` | UUID | yes | unique per session; the database enforces uniqueness |
| `content` | string | yes | non-empty after trim |
| `content_version` | int | yes | 1 on insert; never updated |
| `submitted_at` | datetime | yes | UTC; the actual submission timestamp |
| `submission_status` | enum | yes | `on_time` or `late` (FR-025) |
| `submitted_before_session_start` | bool | yes | FR-025a |
| `reminder_id` | UUID | no | the reminder the user relied on (if any) |
| `created_at` | datetime | yes | |

**Validation rules**:
- Insert is rejected if `session_id` already has a `daily_summary`
  (FR-024a).
- `content` MUST be non-empty after whitespace trim (FR-023).
- `submission_status` is computed at insert time and is immutable.

**Derivation**:
- `on_time` ⇔ `submitted_at <= scheduled_end_at + 30 min` (user tz,
  FR-025).
- `submitted_before_session_start` ⇔ `submitted_at < scheduled_start_at`
  (FR-025a).

**Relationships**:
- One `daily_summary` has zero or one `daily_material`.
- One `daily_summary` is the parent of zero or many `summary_chunks`.

### `daily_materials`

Reading and writing exercises generated from a `daily_summary` (US-5,
FR-032–FR-037). Approval is enforced through the `evaluation_id`
relationship; a material without an `approved` evaluation is never
delivered to the user (FR-042).

| Field | Type | Required | Notes |
|---|---|---|---|
| `_id` | UUID | | |
| `owner_user_id` | UUID | yes | |
| `summary_id` | UUID | yes | FK to `daily_summaries` (unique per summary) |
| `reading` | object | yes | structured reading content |
| `writing_exercises` | array | yes | structured exercises |
| `generation_id` | UUID | yes | FK to `content_generations` |
| `evaluation_id` | UUID | yes | FK to `content_evaluations` |
| `approved_at` | datetime | no | set when the linked evaluation is `approved` |
| `created_at` | datetime | yes | |
| `content_version` | int | yes | 1 on first approval; increments only on a new approved revision (not on the original rejection → revision path) |

**State transitions**:
- `pending_evaluation` → `approved` (linked evaluation is `approved`).
- `pending_evaluation` → `rejected` (a corrective revision is in flight;
  the existing material record is replaced when a new one is approved).

**Relationships**:
- One `daily_material` has exactly one `content_generation` and exactly
  one `content_evaluation`.

### `weekly_summaries`

The consolidated rollup for a Monday-start week in the user's tz
(FR-047, FR-051).

| Field | Type | Required | Notes |
|---|---|---|---|
| `_id` | UUID | | |
| `owner_user_id` | UUID | yes | |
| `week_start_at` | datetime | yes | Monday 00:00 in the user's tz, stored as UTC |
| `week_end_at` | datetime | yes | next Monday 00:00 in the user's tz |
| `on_time_count` | int | yes | |
| `late_count` | int | yes | |
| `missing_count` | int | yes | |
| `recorded_study_minutes` | int | yes | sum of session durations for which a summary exists |
| `consistency_indicators` | object | yes | the three-dimension structure described in FR-067 |
| `knowledge_synthesis` | string | yes | natural-language summary of the week's concepts |
| `weekly_material_id` | UUID | no | FK to `weekly_materials` (only present if a material was approved) |
| `created_at` | datetime | yes | |

**Uniqueness**: `(owner_user_id, week_start_at)` is unique.

### `weekly_materials`

Integrated weekly reading and writing exercises (FR-048). Same shape and
approval rules as `daily_materials`.

| Field | Type | Required | Notes |
|---|---|---|---|
| `_id` | UUID | | |
| `owner_user_id` | UUID | yes | |
| `weekly_summary_id` | UUID | yes | FK to `weekly_summaries` (unique) |
| `reading` | object | yes | |
| `writing_exercises` | array | yes | |
| `generation_id` | UUID | yes | |
| `evaluation_id` | UUID | yes | |
| `approved_at` | datetime | no | |
| `content_version` | int | yes | |
| `created_at` | datetime | yes | |

### `monthly_summaries`

Calendar-month rollup in the user's tz (FR-049, FR-051).

| Field | Type | Required | Notes |
|---|---|---|---|
| `_id` | UUID | | |
| `owner_user_id` | UUID | yes | |
| `month_start_at` | datetime | yes | 1st of the month, 00:00 in the user's tz, stored as UTC |
| `month_end_at` | datetime | yes | 1st of next month, 00:00 in the user's tz |
| `on_time_count` | int | yes | |
| `late_count` | int | yes | |
| `missing_count` | int | yes | |
| `recorded_study_minutes` | int | yes | |
| `consistency_indicators` | object | yes | |
| `knowledge_synthesis` | string | yes | |
| `monthly_material_id` | UUID | no | FK to `monthly_materials` |
| `created_at` | datetime | yes | |

**Uniqueness**: `(owner_user_id, month_start_at)` is unique.

### `monthly_materials`

Same shape and approval rules as `weekly_materials` (FR-050).

### `assistant_threads`

A user's conversation with the AI assistant (US-9). Text-only (FR-065).

| Field | Type | Required | Notes |
|---|---|---|---|
| `_id` | UUID | | |
| `owner_user_id` | UUID | yes | |
| `messages` | array | yes | ordered list of message objects |
| `retrieved_context_refs` | array | no | list of `summary_chunk_id` values used as RAG context |
| `created_at` | datetime | yes | |
| `updated_at` | datetime | yes | |

**Message shape**:
| Field | Type | Notes |
|---|---|---|
| `role` | enum | `user` or `assistant` |
| `content` | string | text-only |
| `sent_at` | datetime | UTC |

### `content_generations`

The output of the Content Generation Model (FR-039). Stored so that the
Content Evaluation Model can be re-run for audit (FR-045).

| Field | Type | Required | Notes |
|---|---|---|---|
| `_id` | UUID | | |
| `owner_user_id` | UUID | yes | |
| `inputs` | object | yes | CEFR level, activity purpose, history slice, period objective |
| `model_id` | string | yes | identifier of the generation model |
| `raw_output` | string | yes | the model's raw response |
| `created_at` | datetime | yes | |

### `content_evaluations`

The structured result of the Content Evaluation Model (FR-041, FR-045).
The verdict is the only field that determines whether the material is
delivered (FR-042).

| Field | Type | Required | Notes |
|---|---|---|---|
| `_id` | UUID | | |
| `owner_user_id` | UUID | yes | |
| `generation_id` | UUID | yes | FK to `content_generations` |
| `model_id` | string | yes | identifier of the evaluation model |
| `verdict` | enum | yes | `approved` or `rejected` |
| `criterion_assessments` | object | yes | per-criterion assessment (vocabulary, grammar, sentence length, reading demands, writing demands, relevance) |
| `rationale` | string | yes | natural-language explanation |
| `attempt_number` | int | yes | 1-based; increments across the corrective loop |
| `created_at` | datetime | yes | |

### `summary_chunks`

Derived data: a chunked piece of a `daily_summary` for vector retrieval
(US-9, RAG architecture). The vector representation never replaces the
original summary (plan §3.2).

| Field | Type | Required | Notes |
|---|---|---|---|
| `_id` | UUID | | |
| `owner_user_id` | UUID | yes | per-user isolation in retrieval |
| `summary_id` | UUID | yes | FK to `daily_summaries` |
| `summary_content_version` | int | yes | matches the parent summary's `content_version` |
| `chunk_index` | int | yes | ordering within the parent summary |
| `text` | string | yes | the chunk's text |
| `token_count` | int | yes | for budget enforcement |
| `embedding_model_id` | string | yes | identifier of the embedding model |
| `embedding` | array of float | yes | the vector |
| `embedding_dim` | int | yes | for index validation |
| `is_obsolete` | bool | yes | true when the parent summary is replaced or a re-embedding supersedes this chunk |
| `created_at` | datetime | yes | |

**Metadata guarantees** (plan §3.2): identifies the parent summary, the
owner, supports filtering, tracks the source content version, supports
reindexing/removal of obsolete chunks. Per-user isolation is enforced
through `owner_user_id`.

**Reindexing**:
- When a new chunk is inserted for a given `(summary_id,
  summary_content_version)`, the previous chunk for the same
  `(summary_id, summary_content_version, chunk_index)` MUST be marked
  `is_obsolete = true` and scheduled for removal.
- Because `daily_summaries` is append-only in this release, reindexing is
  only triggered by embedding-model changes (deferred).

### `feature_availability_config`

Per-feature on/off configuration (US-13). Initial release supports a
global on/off switch (A-8). Per-user overrides are a forward concern
(FR-081).

| Field | Type | Required | Notes |
|---|---|---|---|
| `_id` | string | yes | feature identifier (e.g., `reminders`, `weekly_summaries`) |
| `enabled` | bool | yes | |
| `updated_at` | datetime | yes | |
| `updated_by` | string | yes | who changed it (system or admin user) |

### `audit_events`

Append-only log for the constitution's observability and auditability
requirements (FR-084–FR-086, principle X).

| Field | Type | Required | Notes |
|---|---|---|---|
| `_id` | UUID | | |
| `owner_user_id` | UUID | no | null for system events |
| `event_type` | enum | yes | e.g., `reminder.produced`, `summary.submitted`, `content.generated`, `content.evaluated`, `assistant.turn` |
| `payload` | object | yes | structured event data (no PII or secret values) |
| `created_at` | datetime | yes | |

## State machine: summary → material approval

```
[summary submitted]
        |
        v
[generation request] -> [content_generation] -> [content_evaluation]
        ^                                                |
        |                                                v
        +----- (rejected) ----+            (approved) -> [material approved] -> [material delivered]
                                (bounded by retry limit)
```

The corrective loop is bounded; the bound is configurable per environment
(plan §3.3, A-10). The `attempt_number` on `content_evaluations` is the
audit trail of the loop.

## Indexes (deferred to `tasks.md`)

The plan defers exact indexes. The mandatory index classes are:

- `users`: unique on `email`; index on `time_zone`.
- `daily_summaries`: unique on `session_id`; index on
  `(owner_user_id, submitted_at)`.
- `daily_materials`: unique on `summary_id`; index on
  `(owner_user_id, approved_at)`.
- `summary_chunks`: index on `(owner_user_id, is_obsolete)`;
  vector index on `embedding` (Atlas adapter only).
- `weekly_summaries`, `monthly_summaries`: unique on
  `(owner_user_id, period_start)`.
- All collections: index on `owner_user_id` to enforce per-user scoping
  at the persistence layer.

These are recorded here so the indexes are traceable to the queries the
application issues. The concrete index definitions are produced in
`tasks.md`.
