#!/usr/bin/env bash
# Initialize the emulated AWS Secrets Manager (LocalStack) with the dummy
# local secret inventory (T008).
#
# Every value is `dummy-` prefixed: none of these values can grant access to
# a real external resource (plan.md § Constraints).
#
# The script is IDEMPOTENT: running it twice produces the same final state.

set -euo pipefail

ENDPOINT="${SECRETS_ENDPOINT_URL:-http://localhost:4566}"

# Mandatory local secret inventory (placeholder names per plan.md
# § Open Decisions, item 9). Names here are the single source of truth.
SECRETS=(
  "improve/auth/token-signing-key"
  "improve/ai/generation-model-api-key"
  "improve/ai/evaluation-model-api-key"
  "improve/ai/embedding-api-key"
  "improve/email/ses-smtp-credentials"
)

for secret in "${SECRETS[@]}"; do
  # Create if absent; then force the same dummy value either way, so a
  # second run converges to an identical final state.
  if ! awslocal --endpoint-url="$ENDPOINT" secretsmanager describe-secret \
        --secret-id "$secret" >/dev/null 2>&1; then
    awslocal --endpoint-url="$ENDPOINT" secretsmanager create-secret \
      --name "$secret" \
      --secret-string "dummy-${secret//\//_}" >/dev/null
  else
    awslocal --endpoint-url="$ENDPOINT" secretsmanager put-secret-value \
      --secret-id "$secret" \
      --secret-string "dummy-${secret//\//_}" >/dev/null
  fi
  echo "secret ok: $secret"
done

echo "LocalStack secret initialization complete (idempotent)."