# Quickstart: Improve Lessons Backend

**Phase**: 1 — Runnable validation guide
**Date**: 2026-10-13

This document describes how to bring the local environment up, run the
test suite, and exercise the feature end-to-end. It is the runbook for
the initial release. Implementation details belong in `tasks.md`; this
guide explains how to verify that the implementation works.

## Prerequisites

- Docker Engine 24+ and Docker Compose v2.
- Python 3.14.8 available if running the test suite on the host (the
  `test` Docker target is the supported path).
- `uv` (https://github.com/astral-sh/uv) for local Python dependency
  management.
- `curl` and `jq` for ad-hoc API checks.

## 1. Initialize the local environment

```bash
./init.sh
```

What `init.sh` does:
1. Verifies that Docker and `docker compose` are available.
2. Starts MongoDB and LocalStack.
3. Waits for both services to report healthy.
4. Runs `scripts/init-localstack.sh` to create and validate the local
   secrets in the emulated AWS Secrets Manager.
5. Starts the FastAPI backend (`dev` target) once its dependencies are
   ready.

The script is idempotent: running it twice with the same state succeeds
without duplicating resources.

## 2. Verify the service is up

```bash
curl -fsS http://localhost:8000/api/v1/system/health | jq
```

Expected response:
```json
{
  "status": "ok"
}
```

## 3. Run the test suite

The standard test command is documented in the user-supplied plan:

```bash
docker compose run --rm test
```

Internally this runs:

```bash
python -m unittest discover -s tests
```

The test suite is split into:
- Unit tests for `app/core/`, `app/services/`, and strategies.
- Integration tests for the MongoDB adapters (real MongoDB, isolated
  database per test run).
- API tests using `fastapi.testclient.TestClient`.
- VCR-recorded tests for outbound HTTP integrations (AI provider, email
  provider).
- Idempotency, retry-bound, and user-isolation tests.
- Image-content tests that build the `dev`, `test`, and `runtime`
  Docker targets and assert that the runtime target does not contain
  test code or `requirements_test.txt`.

A clean run prints `OK` and exits 0.

## 4. End-to-end smoke test

This sequence exercises every must-pass behavior from the acceptance
criteria. The numbers below reference the relevant functional
requirements.

```bash
BASE=http://localhost:8000/api/v1

# 4.1 Register and create a session (US-1, US-2)
TOKEN=$(curl -fsS -X POST $BASE/auth/register \
  -H 'content-type: application/json' \
  -d '{
    "name": "Alex Test",
    "email": "alex@example.com",
    "cefr_level": "A2",
    "time_zone": "America/Bogota"
  }' | jq -r .token)

# 4.2 Create a virtual platform (FR-012)
PLATFORM_ID=$(curl -fsS -X POST $BASE/users/me/platforms \
  -H "authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{ "name": "Preply", "url": "https://preply.com" }' | jq -r .id)

# 4.3 Create a schedule (US-2)
SCHEDULE_ID=$(curl -fsS -X POST $BASE/users/me/schedules \
  -H "authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d "{
    \"start_time\": \"07:00\",
    \"end_time\": \"08:00\",
    \"recurrence\": \"daily\",
    \"modality\": \"virtual\",
    \"platform_id\": \"$PLATFORM_ID\"
  }" | jq -r .id)

# 4.4 List today's session
SESSION_ID=$(curl -fsS \
  "$BASE/users/me/sessions?from=$(date -u +%Y-%m-%d)&to=$(date -u +%Y-%m-%d)" \
  -H "authorization: Bearer $TOKEN" | jq -r '.sessions[0].id')

# 4.5 Submit an on-time summary (US-4)
curl -fsS -X POST $BASE/users/me/sessions/$SESSION_ID/summary \
  -H "authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{
    "content": "Today I reviewed the present simple and practiced with adverbs of frequency."
  }' | jq

# 4.6 Confirm the daily material is generated and approved
curl -fsS "$BASE/users/me/sessions/$SESSION_ID/summary/material" \
  -H "authorization: Bearer $TOKEN" | jq

# 4.7 Verify the submission is recorded as on_time
curl -fsS "$BASE/users/me/history/days/$(date -u +%Y-%m-%d)" \
  -H "authorization: Bearer $TOKEN" | jq

# 4.8 Ask the assistant a question (US-9)
THREAD_ID=$(curl -fsS -X POST $BASE/users/me/assistant/threads \
  -H "authorization: Bearer $TOKEN" | jq -r .id)

curl -fsS -X POST $BASE/users/me/assistant/threads/$THREAD_ID/messages \
  -H "authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{ "content": "Can you explain adverbs of frequency?" }' | jq
```

The smoke test fails fast if any of the following are broken:
- Registration with CEFR/time-zone validation.
- Schedule → session expansion in the user's time zone.
- The 30-minute on-time window.
- The two-model content workflow (the material must arrive with an
  `approved` evaluation; the script will return an empty body if the
  evaluation is still pending).
- Per-user isolation in the assistant.

## 5. Validating the Docker image targets

```bash
# Build each target
docker build --target dev      -t improve-lessons-backend:dev      .
docker build --target test     -t improve-lessons-backend:test     .
docker build --target runtime  -t improve-lessons-backend:runtime  .

# The runtime image MUST NOT contain test code or test dependencies
docker run --rm improve-lessons-backend:runtime \
  python -c "import os; assert not os.path.exists('tests'); \
             assert not os.path.exists('requirements_test.txt'); \
             print('runtime image OK')"
```

A passing run prints `runtime image OK`.

## 6. Verifying LocalStack secrets

```bash
aws --endpoint-url=http://localhost:4566 secretsmanager list-secrets \
  --query 'SecretList[].Name'
```

The list MUST include every secret required by the application
configuration. `scripts/init-localstack.sh` is the single source of
truth for the secret names; running it twice is safe.

## 6b. Receiving REAL emails locally (SES → SMTP bridge)

LocalStack community SES accepts `SendEmail` but never delivers to a real
mailbox. In development, when `SMTP_HOST` is configured, the backend
decorates the SES sender with a bridge that forwards the same message to a
real SMTP server (internal postfix/mailutils, etc.) — so reminder emails
produced by local functional tests land in an actual inbox. `SMTP_HOST=""
`` (the default) disables the bridge and keeps behavior identical.

```bash
# Point the backend at an SMTP target (example: a debug receiver on the host)
SMTP_HOST=host.docker.internal SMTP_PORT=1025 docker compose up -d --build backend

# Or forward to a remote postfix instance
SMTP_HOST=<your-smtp-server> SMTP_PORT=25 docker compose up -d backend
```

- Both channels run independently with contained failures: the SES leg
  (LocalStack `SendEmail`, visible via `MessageId` in the logs) is always
  attempted, then the real SMTP forward; neither failure blocks the other.
- `SMTP_USER`/`SMTP_PASSWORD` enable STARTTLS + login for SMTP servers
  that require auth; an internal postfix usually needs none.
- Success lines in the backend logs: `email delivered | to=... message_id=...`
  (SES channel) and `email delivered | to=... channel=smtp` (real forward).
- A throwaway debug receiver for quick verification (tool, not a project
  dependency): `uvx aiosmtpd -n -l 0.0.0.0:1025`.

## 6c. Running the REAL AI models (Ollama)

The content workflow runs TWO different models: `minimax-m3.1-flash:cloud`
generates the material and `glm-5.3-flash:cloud` evaluates it against the
six CEFR criteria. Both are served by Ollama through its native API
(`POST /api/chat`); both are `:cloud` models, so Ollama proxies them to
the provider's cloud and they do not consume the host's hardware.

```bash
# Option A (recommended): Ollama as a Compose service
docker compose --profile ai up -d ollama
docker exec -it improve_lessons_backend-ollama-1 ollama pull minimax-m3.1-flash:cloud
docker exec -it improve_lessons_backend-ollama-1 ollama pull glm-5.3-flash:cloud
AI_BASE_URL=http://ollama:11434 docker compose up -d --build backend

# Option B: the host's Ollama (must listen on more than 127.0.0.1)
ollama pull minimax-m3.1-flash:cloud
ollama pull glm-5.3-flash:cloud
docker compose up -d --build backend
```

**The host's Ollama must accept connections from the container.** By
default `ollama serve` listens on `127.0.0.1` only, which the container
cannot reach — the priming then logs
`ai provider priming failed | error=... Connection refused` and the
backend falls back to the deterministic pair. Either use the Compose
`ollama` service (option A, reached by service name on the Compose
network) or let the host's Ollama listen on the bridge interface
(`OLLAMA_HOST=0.0.0.0:11434 ollama serve`). The latter exposes the model
server on every host interface, so do it only on a machine whose network
you trust.

Configuration (all optional — the defaults match the values above):

| Variable | Default | Purpose |
|---|---|---|
| `AI_PROVIDER` | `ollama` | `deterministic` forces the offline stub pair |
| `AI_BASE_URL` | `http://host.docker.internal:11434` | the Ollama server (`http://ollama:11434` with the Compose service) |
| `AI_GENERATION_MODEL` | `minimax-m3.1-flash:cloud` | the generation model |
| `AI_EVALUATION_MODEL` | `glm-5.3-flash:cloud` | the evaluation model |
| `AI_GENERATION_MAX_TOKENS` | `8000` | generation token budget |
| `AI_EVALUATION_MAX_TOKENS` | `6000` | evaluation token budget |
| `AI_REQUEST_TIMEOUT_SECONDS` | `180` | per-request timeout |
| `AI_KEEP_ALIVE` | `10m` | how long Ollama keeps the model loaded |

- In a real environment, `AI_BASE_URL` is the provider's network
  hostname — never `127.0.0.1`, which inside a container is the container
  itself.
- Ollama does not authenticate, so no secret is resolved for it.
- At startup the backend primes the provider: outside development/test an
  unreachable provider fails startup (fail fast); in development the
  failure is logged and the deterministic pair takes over.
- The two models have separate roles, separate system prompts and
  separate clients (constitution principle II). The evaluator's verdict
  is fail-closed: a material is approved only when all six criteria are
  present and passing.
- The test suite never touches the provider: the provider exchanges are
  replayed from VCR cassettes under `tests/vcr_cassettes/`.

## 7. Resetting the environment

```bash
docker compose down -v
./init.sh
```

This drops all containers, volumes, and LocalStack state, then re-runs
the full initialization.

## 8. What "working" means for this release

- The smoke test in §4 completes end-to-end.
- The test command in §3 reports zero failures.
- The runtime image assertion in §5 passes.
- The LocalStack secret list in §6 contains every required secret.
- No real credentials are committed; `git grep -nE 'AKIA[0-9A-Z]{16}'`
  returns no matches in tracked files.
- The UTC-standard checks in §9 all pass.

If all of the above hold, the initial release is ready for the
`/speckit-tasks` workflow.

## 9. UTC standard validation

The "Date and Time Handling — Mandatory UTC Standard" (`plan.md` §
Mandatory Standards) requires the following automated checks. They
run as part of the standard test suite and additionally as part of the
runtime image validation.

### 9.1 API contract checks

```bash
# Reject naive timestamps
curl -i -X POST $BASE/users/me/sessions/$SESSION_ID/summary \
  -H "authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"content": "...", "submitted_at": "2026-10-13T10:30:00"}' | grep '400'

# Accept and normalize an offset-bearing timestamp
curl -fsS -X POST $BASE/users/me/sessions/$SESSION_ID/summary \
  -H "authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"content": "...", "submitted_at": "2026-10-13T10:30:00-04:00"}' | jq .submitted_at
# Expected: "2026-10-13T14:30:00Z"
```

### 9.2 Persistence and adapter checks

The MongoDB adapter integration tests assert that:

- Every persisted datetime is stored as a BSON `Date` (UTC by definition)
  and is read back as a timezone-aware `datetime` in UTC.
- The adapter raises a domain-specific error when a caller attempts to
  persist a naive datetime.
- A user in `America/Bogota` with a session that crosses a DST
  boundary keeps the correct on-time/late classification
  (UTC normalization is independent of the user's local clock).

### 9.3 Static lint

A static test in the test suite fails the build if any of the following
appears in `app/` outside `app/core/time/`:

- `datetime.now(` without an explicit `tz=` argument
- `import pytz`
- `astimezone(` to a non-UTC zone

```bash
python -m unittest discover -s tests -k test_no_implicit_local_time
```

### 9.4 Logging

The test suite asserts that the `asctime` in every captured log record
ends with `Z` and is a valid UTC instant, regardless of the host's
local time zone.

### 9.5 Runtime image

```bash
# The runtime image MUST NOT contain test code or test dependencies
docker run --rm improve-lessons-backend:runtime \
  python -c "import os; assert not os.path.exists('tests'); \
             assert not os.path.exists('requirements_test.txt'); \
             print('runtime image OK')"

# The runtime image's logging format MUST emit a Z-suffixed UTC timestamp
docker run --rm improve-lessons-backend:runtime \
  python -c "import logging; from app.utils.logging import configure; \
             configure(); logging.getLogger('check').info('utc-ok')" \
  2>&1 | grep -E 'Z$|UTC-ok'
```

If any of §9.1–§9.5 fails, the release is not ready.
