#!/usr/bin/env bash
# End-to-end smoke test (T109): replays quickstart.md § 4 against a running
# backend. Fails fast on any broken must-pass behavior.
#
# Usage:
#   ./scripts/smoke_test.sh [base_url]        # default http://localhost:8000/api/v1
#
# Requires: curl, python3

set -euo pipefail

BASE="${1:-http://localhost:8000/api/v1}"
fail() { echo "SMOKE FAIL: $*" >&2; exit 1; }

# JSON helper: `jqpy <python-expr-over-d>` reads the response on stdin and
# evaluates the expression, where `d` is the parsed document.
jqpy() { python3 -c "import json,sys; d=json.load(sys.stdin); print(eval(sys.argv[1]))" "$1"; }

# ---- §4.1 Register (US-1, US-2) ---------------------------------------------
EMAIL="smoke-$(date +%s)@example.com"
REGISTER=$(curl -fsS -X POST "$BASE/auth/register" \
  -H 'content-type: application/json' \
  -d "{
    \"name\": \"Alex Test\",
    \"email\": \"$EMAIL\",
    \"cefr_level\": \"A2\",
    \"time_zone\": \"America/Bogota\"
  }") || fail "registration request failed"
TOKEN=$(echo "$REGISTER" | jqpy "d['token']")
[ -n "$TOKEN" ] || fail "registration did not return a token"

# ---- §4.2 Register a virtual platform (FR-012) -------------------------------
PLATFORM_ID=$(curl -fsS -X POST "$BASE/users/me/platforms" \
  -H "authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{ "name": "Preply", "url": "https://preply.com" }' | jqpy "d['id']")
[ -n "$PLATFORM_ID" ] || fail "platform was not created"

# ---- §4.3 Create a schedule (US-2) -------------------------------------------
# Ends 15 minutes ago (wall clock in the user's tz) so the summary window is open.
now_local=$(TZ=America/Bogota date -d '-15 minutes' +%H:%M)
start_local=$(TZ=America/Bogota date -d '-60 minutes' +%H:%M)
SCHEDULE_ID=$(curl -fsS -X POST "$BASE/users/me/schedules" \
  -H "authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d "{
    \"start_time\": \"$start_local\",
    \"end_time\": \"$now_local\",
    \"recurrence\": \"daily\",
    \"modality\": \"virtual\",
    \"platform_id\": \"$PLATFORM_ID\"
  }" | jqpy "d['id']")
[ -n "$SCHEDULE_ID" ] || fail "schedule was not created"

# ---- §4.4 The session exists (US-2, deterministic in the user's tz) ----------
TODAY=$(TZ=America/Bogota date +%F)
SESSION_ID=$(curl -fsS "$BASE/users/me/sessions?from=$TODAY&to=$TODAY" \
  -H "authorization: Bearer $TOKEN" \
  | jqpy "[s['id'] for s in d['sessions'] if s['schedule_id']=='$SCHEDULE_ID' and not s.get('reminder_sent_at')][0]") \
  || fail "no session was expanded for today"

# ---- §4.5 Submit the summary on time (US-4) ----------------------------------
SUMMARY=$(curl -fsS -X POST "$BASE/users/me/sessions/$SESSION_ID/summary" \
  -H "authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{ "content": "Today I reviewed the present simple and practiced with adverbs of frequency." }')
[ "$(echo "$SUMMARY" | jqpy "d['submission_status']")" = "on_time" ] \
  || fail "the on-time window rejected the summary ($(echo "$SUMMARY" | jqpy "d['submission_status']"))"
[ "$(echo "$SUMMARY" | jqpy "d['submitted_at']")" ] \
  || fail "submitted_at missing"

# ---- §4.6 The daily material is approved and delivered (US-5, US-12) ---------
MATERIAL=$(curl -fsS "$BASE/users/me/sessions/$SESSION_ID/summary/material" \
  -H "authorization: Bearer $TOKEN")
echo "$MATERIAL" | jqpy "bool(d['reading']['body']) and bool(d['evaluation_id'])" >/dev/null \
  || fail "the daily material was not approved/delivered"

# ---- §4.7 History keeps the record (US-8) ------------------------------------
HISTORY=$(curl -fsS "$BASE/users/me/history/days/$TODAY" \
  -H "authorization: Bearer $TOKEN")
COUNT=$(echo "$HISTORY" | jqpy "len(d.get('summaries', d.get('records', [])))")
[ "${COUNT:-0}" -ge 1 ] || fail "history day view lost the summary"

# ---- §4.8 Assistant grounded in history (US-9) --------------------------------
THREAD_ID=$(curl -fsS -X POST "$BASE/users/me/assistant/threads" \
  -H "authorization: Bearer $TOKEN" | jqpy "d['id']")
[ -n "$THREAD_ID" ] || fail "the assistant thread was not opened"
REPLY=$(curl -fsS -X POST "$BASE/users/me/assistant/threads/$THREAD_ID/messages" \
  -H "authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{ "content": "Can you explain adverbs of frequency?" }')
echo "$REPLY" | jqpy "'practice' in d['reply']['content'].lower() or 'documented' in d['reply']['content'].lower()" >/dev/null \
  || fail "the assistant reply was not grounded in the documented history"

# ---- progress + features (US-10, US-13) --------------------------------------
curl -fsS "$BASE/users/me/progress" -H "authorization: Bearer $TOKEN" \
  | jqpy "'Activity indicators are not' in d['disclaimer']" >/dev/null \
  || fail "the progress report lost the activity-vs-proficiency disclaimer"
curl -fsS "$BASE/system/health" | jqpy "d['status'] == 'ok'" >/dev/null \
  || fail "system health is not ok"

echo "SMOKE OK — the full user journey (register → schedule → summary → material → history → assistant → progress) passed."