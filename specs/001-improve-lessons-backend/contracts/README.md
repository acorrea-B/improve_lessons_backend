# API Contracts: Improve Lessons Backend

**Phase**: 1 — Public API surface
**Date**: 2026-10-13
**Base URL**: `/api/v1`

This document defines the HTTP API exposed by `improve_lessons_backend`. The
endpoints implement the user stories (US-1 through US-13) in the functional
specification. Each endpoint is documented with its method, path,
authentication requirements, request body, response body, and error
semantics. The contract is intentionally implementation-agnostic; it is
the source of truth for both the FastAPI layer and the test suite.

## Conventions

- **Versioning**: every endpoint lives under `/api/v1`. Future versions
  introduce a new prefix.
- **Authentication**: every endpoint requires a valid session, unless
  explicitly marked "Public". The exact session mechanism is a deferred
  decision; the contract defines only that an authenticated principal is
  required.
- **Authorization**: the authenticated principal MUST own every resource
  referenced in the URL or body. Cross-user access returns `403 Forbidden`.
- **Time zone and timestamps (mandatory UTC standard)**: all
  date/time fields that represent an instant are expressed in UTC
  using ISO 8601 with the `Z` suffix, e.g., `2026-10-13T14:30:00Z`.
  Responses MUST use the `Z` suffix; explicit offsets such as
  `+00:00` are NOT emitted. Requests MAY include explicit offsets
  (e.g., `2026-10-13T10:30:00-04:00`); such values are normalized to
  UTC before processing or persistence. Requests with naive timestamps
  (no offset) on a field that represents an instant are rejected
  with `400 Bad Request` and the standard error envelope. Local
  wall-clock fields (e.g., `start_time: "07:00"` on a schedule) are
  NOT treated as instants and are accepted as `HH:MM` strings. See
  `plan.md` § Mandatory Standards § Date and Time Handling.
- **Idempotency**: every write endpoint accepts an optional
  `Idempotency-Key` header. Repeated writes with the same key return the
  original response.
- **Error envelope**:
  ```json
  {
    "error": {
      "code": "string",
      "message": "string",
      "details": { "field": "string", "issue": "string" }
    }
  }
  ```
- **HTTP status codes**:
  - `200 OK` for successful reads and idempotent updates.
  - `201 Created` for successful resource creation.
  - `204 No Content` for successful operations with no body.
  - `400 Bad Request` for invalid input.
  - `401 Unauthorized` when the request is not authenticated.
  - `403 Forbidden` when the request is authenticated but the principal
    does not own the resource.
  - `404 Not Found` when the resource does not exist.
  - `409 Conflict` for state-machine conflicts (e.g., duplicate summary).
  - `422 Unprocessable Entity` for validation failures with field-level
    detail.
  - `503 Service Unavailable` for transient infrastructure failures with
    a `Retry-After` header.

## Endpoints

### Authentication

The exact authentication mechanism is deferred. The contract defines the
endpoints that authentication is expected to expose; concrete routes are
added once the mechanism is chosen.

- `POST /auth/register` (public) — create a user account (US-1).
- `POST /auth/login` (public) — exchange credentials for a session.
- `POST /auth/logout` — invalidate the current session.
- `GET /auth/me` — return the authenticated user's profile.

### Users (US-1)

- `GET /users/me` — fetch the authenticated user's profile.
- `PATCH /users/me` — update `name`, `preferred_name`, `email`, `cefr_level`,
  or `time_zone`. The previous values are appended to `users_profile_history`.

### External learning platforms (US-2)

- `GET /users/me/platforms` — list the platforms the user has registered.
- `POST /users/me/platforms` — register a new platform (FR-012).
- `DELETE /users/me/platforms/{platform_id}` — remove a platform. Fails
  with `409 Conflict` if a `schedule` still references it.

### Schedules (US-2)

- `GET /users/me/schedules` — list the user's schedules.
- `POST /users/me/schedules` — create a schedule.
- `GET /users/me/schedules/{schedule_id}` — fetch one schedule.
- `PATCH /users/me/schedules/{schedule_id}` — update a schedule. Edits
  apply to future sessions only; historical sessions are unchanged.
- `DELETE /users/me/schedules/{schedule_id}` — delete a schedule. Future
  sessions are removed; historical sessions are retained.

### Sessions

Sessions are derived from schedules and are read-only.

- `GET /users/me/sessions?from=YYYY-MM-DD&to=YYYY-MM-DD` — list sessions in
  a date range. Date range is interpreted in the user's time zone.
- `GET /users/me/sessions/{session_id}` — fetch one session, including its
  modality-specific information.

### Daily summaries (US-4)

- `POST /users/me/sessions/{session_id}/summary` — submit a daily summary.
  - Request: `{ "content": "string" }`.
  - Returns `201` with the new summary document, including the derived
    `submission_status` and the `submitted_before_session_start` flag.
  - Returns `409` if a summary already exists for the session (FR-024a).
  - Returns `422` if `content` is empty after trim.
- `GET /users/me/summaries/{summary_id}` — fetch a summary.
- `GET /users/me/summaries?from=YYYY-MM-DD&to=YYYY-MM-DD` — list summaries
  in a date range.

### Daily materials (US-5)

- `GET /users/me/summaries/{summary_id}/material` — fetch the approved
  material for a summary. Returns `404` if no material is yet approved.
- `GET /users/me/daily-materials?from=YYYY-MM-DD&to=YYYY-MM-DD` — list
  approved daily materials in a date range.

### Weekly summaries (US-6)

- `GET /users/me/weekly-summaries?from=YYYY-MM-DD&to=YYYY-MM-DD` — list
  weekly summaries in a date range. Date range is interpreted in the
  user's time zone; weekly boundaries are Monday 00:00 → next Monday 00:00.
- `GET /users/me/weekly-summaries/{weekly_summary_id}` — fetch one
  weekly summary.
- `GET /users/me/weekly-summaries/{weekly_summary_id}/material` — fetch
  the approved weekly material, if any.

### Monthly summaries (US-7)

- `GET /users/me/monthly-summaries?from=YYYY-MM-DD&to=YYYY-MM-DD` — list
  monthly summaries in a date range. Boundaries are calendar months in
  the user's time zone.
- `GET /users/me/monthly-summaries/{monthly_summary_id}` — fetch one
  monthly summary.
- `GET /users/me/monthly-summaries/{monthly_summary_id}/material` — fetch
  the approved monthly material, if any.

### Learning history (US-8)

- `GET /users/me/history?from=YYYY-MM-DD&to=YYYY-MM-DD` — list everything
  in the date range: daily summaries, daily materials, weekly summaries
  with materials, monthly summaries with materials. Late submissions
  appear with `submission_status = "late"`.
- `GET /users/me/history/days/{YYYY-MM-DD}` — fetch a specific day.
- `GET /users/me/history/weeks/{YYYY-MM-DD}` — fetch a specific week
  (the day must be a Monday in the user's time zone).
- `GET /users/me/history/months/{YYYY-MM}` — fetch a specific month.

### Personalized AI assistant (US-9)

- `POST /users/me/assistant/threads` — open a new thread.
- `GET /users/me/assistant/threads` — list the user's threads.
- `GET /users/me/assistant/threads/{thread_id}` — fetch a thread.
- `POST /users/me/assistant/threads/{thread_id}/messages` — append a user
  message and return the assistant's reply. The assistant's response is
  generated synchronously; long generations are an explicit forward
  concern.
- `DELETE /users/me/assistant/threads/{thread_id}` — delete a thread.

### Progress indicators (US-10)

- `GET /users/me/progress` — fetch the three-dimension progress report.
  Returns the reading, writing, and consistency sections explicitly, with
  the disclaimer that the indicators are activity signals unless otherwise
  stated.
- `GET /users/me/progress/streaks` — fetch the user's current
  on-time submission streak and the longest streak in history.

### Motivation and progressive challenges (US-11)

- `GET /users/me/recognitions` — fetch the user's recognitions
  (achievements, streaks, etc.).
- `GET /users/me/challenges` — fetch the next recommended challenge.
  Honors the constitution's "do not exceed CEFR by more than one level"
  rule (FR-075).
- `POST /users/me/challenges/{challenge_id}/start` — start a challenge
  as a daily/weekly/monthly material. The challenge material is
  generated through the standard two-model workflow.

### Feature availability (US-13)

- `GET /system/features` — list the available features and their current
  state. Public; no authentication required.
- `GET /system/health` — public health check. Returns `200` with
  `{ "status": "ok" }` when the application is ready to serve.

## Sample request/response shapes

### `POST /users/me/sessions/{session_id}/summary`

Request:
```json
{
  "content": "Today I learned the present simple and how to use it with adverbs of frequency."
}
```

Response (201 Created):
```json
{
  "id": "0d6c2c1a-1c1a-4b1a-9f1a-1a1a1a1a1a1a",
  "session_id": "1f1a1a1a-1a1a-4a1a-8a1a-1a1a1a1a1a1a",
  "content": "Today I learned the present simple...",
  "submitted_at": "2026-10-13T13:34:12Z",
  "submission_status": "on_time",
  "submitted_before_session_start": false,
  "owner_user_id": "a1a1a1a1-a1a1-4a1a-8a1a-a1a1a1a1a1a1"
}
```

Error response (409 Conflict, duplicate):
```json
{
  "error": {
    "code": "summary_already_exists",
    "message": "A summary for this session has already been submitted."
  }
}
```

### `GET /users/me/progress`

Response (200 OK):
```json
{
  "reading": {
    "summary": "Based on 14 reading activities over the last 30 days.",
    "indicators": {
      "activities_completed": 14,
      "average_cefr_within_target": 0.93
    },
    "disclaimer": "Reading indicators reflect activity signals, not formal proficiency."
  },
  "writing": {
    "summary": "Based on 12 writing exercises over the last 30 days.",
    "indicators": {
      "exercises_completed": 12
    },
    "disclaimer": "Writing indicators reflect activity signals, not formal proficiency."
  },
  "consistency": {
    "summary": "On-time streak: 4 sessions. Longest streak: 11 sessions.",
    "indicators": {
      "on_time_streak": 4,
      "longest_on_time_streak": 11,
      "on_time_count_30d": 9,
      "late_count_30d": 2,
      "missing_count_30d": 1
    }
  },
  "disclaimer": "Activity indicators are not a formal English proficiency certification."
}
```

## Timestamp examples (mandatory UTC)

The API serializes every instant in UTC with the `Z` suffix. The
following are canonical examples; the test suite uses them as
acceptance fixtures.

| Case | Input | Status | Normalized/serialized form |
|---|---|---|---|
| Response body | — | always | `2026-10-13T14:30:00Z` |
| Request body | `2026-10-13T14:30:00Z` | accepted | `2026-10-13T14:30:00Z` |
| Request body | `2026-10-13T10:30:00-04:00` | accepted, normalized | `2026-10-13T14:30:00Z` |
| Request body | `2026-10-13T10:30:00` (no offset) | rejected | `400 Bad Request` with `error.code = "invalid_timestamp"` |
| Local wall-clock field (`start_time`) | `"07:00"` | accepted | stored as the literal string `07:00`; not converted to an instant |
| Local calendar date field (`date`) | `2026-10-13` | accepted | interpreted as a calendar date in the user's time zone, never converted to an instant without explicit context |

The Pydantic `AwareDatetime` annotation is the only allowed type for
fields that represent instants. It is bound to UTC and emits the `Z`
suffix on serialization. A request model that accepts a timestamp
performs a `before` validator that normalizes explicit offsets and
rejects naive values.

## Cross-cutting requirements

- **Audit logging**: every request that performs a privileged operation
  produces an `audit_events` entry (FR-084–FR-086).
- **Idempotency**: write endpoints accept `Idempotency-Key`. The contract
  guarantees that a repeat with the same key returns the original
  response, not a duplicate.
- **Validation**: request bodies are validated by pydantic models in
  `app/api/v1/requests/`. Field-level errors return `422` with the
  `details` envelope.
- **Rate limiting**: rate limits are enforced at the API layer; limits
  are not exposed in this contract (deferred decision).

## Out of contract (this release)

- Anything listed in the product definition's "Out of Scope" section
  (audio, image, social, payments, native mobile, automatic LMS
  integration).
- Bulk export of a user's data (forward concern).
- Account deletion endpoint (FR-008a, A-16).
- Per-user feature-availability overrides (FR-081).
