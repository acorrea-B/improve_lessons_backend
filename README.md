# improve_lessons_backend

Multi-user FastAPI backend that helps English learners build consistent
study habits, document what they have learned, reinforce it through
personalized reading and writing practice, and progress through the CEFR
levels.

## Prerequisites

- Docker Engine 24+ and Docker Compose v2
- [`uv`](https://github.com/astral-sh/uv) for local dependency management
- Python 3.14.8 (or run everything inside Docker — the supported path)

## Quick start

```bash
./init.sh                       # mongodb + localstack + secrets + backend
curl http://localhost:8000/api/v1/system/health
```

## Testing

The standard test command is:

```bash
python -m unittest discover -s tests
```

or, fully containerized (real MongoDB required for the integration tests):

```bash
docker compose run --rm test
```

## AI provider

The content workflow runs **two different models**: `minimax-m3.1-flash:cloud`
generates the material and `glm-5.3-flash:cloud` evaluates it against the
six CEFR criteria. Both are served by Ollama through its native API, and
both are `:cloud` models (Ollama proxies them to the provider's cloud).

```bash
ollama pull minimax-m3.1-flash:cloud
ollama pull glm-5.3-flash:cloud
docker compose up -d --build backend
```

The backend reaches the host's Ollama through `host.docker.internal`
(the container cannot see the host's `127.0.0.1`); in another environment
set `AI_BASE_URL` to the provider's network hostname. The model pair, the
token budgets and the timeout are all configuration — see
`specs/001-improve-lessons-backend/quickstart.md` § 6c. The test suite
replays the provider exchanges from VCR cassettes, so it never touches
the network.

## Runtime image assertion

The `runtime` Docker target MUST NOT contain test code or
`requirements_test.txt`. Validate with:

```bash
docker build --target runtime -t improve-lessons-backend:runtime .
docker run --rm improve-lessons-backend:runtime \
  python -c "import os; assert not os.path.exists('tests'); \
             assert not os.path.exists('requirements_test.txt'); \
             print('runtime image OK')"
```

See `scripts/image_content_check.sh` for the full content validation.

## Documentation

- [Specification](specs/001-improve-lessons-backend/spec.md)
- [Implementation plan](specs/001-improve-lessons-backend/plan.md)
- [Research decisions](specs/001-improve-lessons-backend/research.md)
- [Data model](specs/001-improve-lessons-backend/data-model.md)
- [API contracts](specs/001-improve-lessons-backend/contracts/README.md)
- [Quickstart runbook](specs/001-improve-lessons-backend/quickstart.md)
- [Tasks](specs/001-improve-lessons-backend/tasks.md)