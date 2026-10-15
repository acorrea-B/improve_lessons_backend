#!/usr/bin/env bash
# Docker image content validation (T111): builds dev/test/runtime targets,
# asserts the runtime target ships no test code or test dependencies, and
# that its logging emits a Z-suffixed UTC timestamp (quickstart § 9.5).

set -euo pipefail
cd "$(dirname "$0")/.."

IMAGE_BASE="${IMAGE_BASE:-improve-lessons-backend}"
DOCKER="${DOCKER:-docker}"
PYTHON="${PYTHON:-python}"
MONGO_URI="${MONGODB_URI:-mongodb://host.docker.internal:27017}"

echo "==> Building dev target"
$DOCKER build --target dev      -t "$IMAGE_BASE:dev"      .
echo "==> Building test target"
$DOCKER build --target test     -t "$IMAGE_BASE:test"     .
echo "==> Building runtime target"
$DOCKER build --target runtime  -t "$IMAGE_BASE:runtime"  .

echo "==> Asserting the runtime target has no test code or test dependencies"
$DOCKER run --rm "$IMAGE_BASE:runtime" \
  python -c "import os; assert not os.path.exists('tests'); \
             assert not os.path.exists('requirements_test.txt'); \
             import pathlib; \
             assert not list(pathlib.Path('app').rglob('test_*')); \
             print('runtime image OK')"

echo "==> Asserting the runtime logging emits a Z-suffixed UTC timestamp"
$DOCKER run --rm -e SECRET_PROVIDER=none "$IMAGE_BASE:runtime" \
  python -c "import logging; from app.utils.logging import configure_logging; \
             logger = configure_logging(); logging.getLogger('improve_lessons').info('utc-ok')" \
  2>&1 | tee /tmp/runtime_log_smoke.txt | grep -E "utc-ok" || true
grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z \|' /tmp/runtime_log_smoke.txt >/dev/null \
  || { echo "image content check FAIL: log line is not Z-suffixed UTC" >&2; exit 1; }

echo "IMAGE CONTENT CHECK: OK (dev/test/runtime built; runtime clean)"