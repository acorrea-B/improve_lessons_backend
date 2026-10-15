#!/usr/bin/env bash
# Local environment orchestration (T009). Idempotent: safe to run repeatedly.
# 1. Verify Docker and docker compose.
# 2. Start MongoDB and LocalStack.
# 3. Wait for both health checks.
# 4. Initialize and validate the LocalStack secrets.
# 5. Start the FastAPI backend (dev target).

set -euo pipefail
cd "$(dirname "$0")"

fail() { echo "init.sh: $*" >&2; exit 1; }

command -v docker >/dev/null 2>&1 || fail "docker is not installed."
docker compose version >/dev/null 2>&1 || fail "docker compose v2 is not available."

echo "==> Starting mongodb and localstack"
docker compose up -d mongodb localstack

echo "==> Waiting for mongodb health check"
for _ in $(seq 1 60); do
  if docker compose ps --format json mongodb 2>/dev/null | grep -q '"Health":"healthy"'; then
    break
  fi
  sleep 2
done
docker compose ps mongodb | grep -q "healthy" || fail "mongodb did not become healthy."

echo "==> Waiting for localstack health check"
for _ in $(seq 1 60); do
  if docker compose ps localstack | grep -q "healthy"; then
    break
  fi
  sleep 2
done
docker compose ps localstack | grep -q "healthy" || fail "localstack did not become healthy."

echo "==> Initializing LocalStack secrets"
docker compose exec -T localstack bash -c \
  "SECRETS_ENDPOINT_URL=http://localhost:4566 bash -s" < scripts/init-localstack.sh

echo "==> Validating mandatory secrets"
HOST_ENDPOINT="http://localhost:4566"
for secret in $(grep -oE '"improve/[^"]+"' scripts/init-localstack.sh | tr -d '"'); do
  if ! docker compose exec -T localstack awslocal --endpoint-url=http://localhost:4566 \
        secretsmanager describe-secret --secret-id "$secret" >/dev/null 2>&1; then
    fail "mandatory secret missing after initialization: $secret"
  fi
done

echo "==> Starting backend (dev target)"
docker compose up -d backend

echo "init.sh: environment is up. Health: curl http://localhost:8000/api/v1/system/health"