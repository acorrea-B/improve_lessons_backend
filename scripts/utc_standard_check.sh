#!/usr/bin/env bash
# UTC standard validation suite (T110): quickstart.md § 9 rules in one
# executable:
#   § 9.1 API contract checks  (naive rejected / offsets normalized)
#   § 9.2 persistence invariants (unit: adapter raises on naive writes,
#          stores/read-backs aware UTC — executed as part of the suite)
#   § 9.3 static lint (unittest -k test_no_implicit_local_time)
#   § 9.4 logging format (Z-suffixed UTC asctime)
#   § 9.5 runtime image check is in scripts/image_content_check.sh

set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PYTHON:-python}"

echo "==> § 9.3 static lint (no implicit local time)"
"$PY" -m unittest tests.core.test_utc_standard -v

echo "==> § 9.1/9.2/9.4 UTC contract, adapter and logging checks"
"$PY" -m unittest \
  tests.api.test_requests_utc \
  tests.core.test_time_helpers \
  tests.core.test_logging_format \
  tests.integration.test_summary_repository \
  -v

echo "UTC STANDARD CHECK: OK"