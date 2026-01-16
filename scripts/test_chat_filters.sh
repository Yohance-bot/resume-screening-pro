#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:5050}"
CHAT_URL="${CHAT_URL:-$API_BASE_URL/api/chat}"
SESSION_ID="${SESSION_ID:-curl-test-session}"

if command -v jq >/dev/null 2>&1; then
  JQ="jq"
else
  JQ="cat"
fi

request() {
  local name="$1"
  local message="$2"

  local tmp_body
  tmp_body="$(mktemp -t chat_body.XXXXXX)"

  echo "\n=== $name ==="
  echo "POST $CHAT_URL"
  echo "message: $message"

  local http_code
  # Don't let one request abort the full smoke test run
  set +e
  http_code=$(curl -sS \
    -o "$tmp_body" \
    -w "%{http_code}" \
    -H "Content-Type: application/json" \
    -X POST \
    --data "{\"message\": \"${message//\"/\\\"}\", \"session_id\": \"$SESSION_ID\"}" \
    "$CHAT_URL")
  local curl_exit=$?
  set -e

  echo "HTTP_STATUS=$http_code"
  if [ "$curl_exit" != "0" ]; then
    echo "CURL_EXIT=$curl_exit"
  fi

  if [ -s "$tmp_body" ]; then
    # Keep output small to avoid pipe/write issues in constrained terminals.
    if command -v jq >/dev/null 2>&1; then
      cat "$tmp_body" | jq '{session_id, message: ((.message // "") | tostring | .[0:400]), structured: (.structured | {type, headers, rows: (.rows[0:2] // .rows // []), applied_filters, warnings, scanned, matched, spec})}'
    else
      head -c 5000 "$tmp_body"; echo
    fi
  else
    echo "<empty body>"
  fi

  rm -f "$tmp_body"
  return 0
}

# 1) Basic chat (should still work; no regressions)
request "1) basic chat" "hello"

# 2) Skills AND skills
request "2) skills AND skills" "candidates with python and aws"

# 3) Certifications AND skill
request "3) cert AND skill" "candidates certified in azure and knows python"

# 4) Experience years AND skill (skip if total_experience_years does not exist)
# Candidate model includes total_experience_years, so run unconditionally.
request "4) years AND skill" "candidates with more than 3 yrs experience and machine learning"

# 5) OR query
request "5) OR query" "candidates with aws or gcp"

# 6) Unknown-field robustness / band bucket
request "6) bucket robustness" "candidates who are c4 and have ml certifications"

# 7) Skill + certification conjunction (python + machine learning certifications)
echo "\n=== 7) python AND ML certifications ==="
tmp_body_assert="$(mktemp -t chat_body.XXXXXX)"
http_code=$(curl -sS -o "$tmp_body_assert" -w "%{http_code}" \
  -H "Content-Type: application/json" \
  -X POST \
  --data '{"message":"candidates who have python and machine learning certifications","session_id":"'$SESSION_ID'"}' \
  "$CHAT_URL")
echo "HTTP_STATUS=$http_code"

if command -v jq >/dev/null 2>&1; then
  cat "$tmp_body_assert" | jq '{session_id, message: ((.message // "") | tostring | .[0:300]), applied_filters: (.structured.applied_filters // [])}'
  has_python=$(cat "$tmp_body_assert" | jq -r '((.structured.applied_filters // []) | tostring | test("python";"i"))')
  has_ml=$(cat "$tmp_body_assert" | jq -r '((.structured.applied_filters // []) | tostring | test("machine learning";"i"))')
  if [ "$has_python" != "true" ] || [ "$has_ml" != "true" ]; then
    echo "ASSERTION_FAILED: expected applied_filters to contain both python and machine learning"
    exit 1
  else
    echo "ASSERTION_PASSED"
  fi
else
  head -c 2000 "$tmp_body_assert"; echo
fi
rm -f "$tmp_body_assert"

# 9) Filter Helper endpoints smoke tests
echo "\n=== 9) filter-options endpoints ==="
for ep in projects skills certifications buckets roles; do
  echo "GET $API_BASE_URL/api/filter-options/$ep"
  tmp_body_assert="$(mktemp -t chat_body.XXXXXX)"
  code=$(curl -sS -o "$tmp_body_assert" -w "%{http_code}" "$API_BASE_URL/api/filter-options/$ep")
  echo "HTTP_STATUS=$code"
  if command -v jq >/dev/null 2>&1; then
    cat "$tmp_body_assert" | jq '.[0:10]'
  else
    head -c 500 "$tmp_body_assert"; echo
  fi
  rm -f "$tmp_body_assert"
done

echo "\n=== 10) structured filter endpoint (/api/candidates/filter) ==="
tmp_body_assert="$(mktemp -t chat_body.XXXXXX)"
payload='{"op":"AND","filters":[{"field":"project","operator":"contains","value":"Grilld"},{"field":"certification","operator":"contains","value":"Machine Learning"}]}'
code=$(curl -sS -o "$tmp_body_assert" -w "%{http_code}" \
  -H "Content-Type: application/json" \
  -X POST \
  --data "$payload" \
  "$API_BASE_URL/api/candidates/filter")
echo "HTTP_STATUS=$code"

if command -v jq >/dev/null 2>&1; then
  cat "$tmp_body_assert" | jq '{message: ((.message // "") | tostring | .[0:200]), structured_type: (.structured.type // null), applied_filters: (.structured.applied_filters // []), matched: (.structured.matched // null)}'
  is_table=$(cat "$tmp_body_assert" | jq -r '(.structured.type // "") == "candidate_table"')
  has_grilld=$(cat "$tmp_body_assert" | jq -r '((.structured.applied_filters // []) | tostring | test("Grilld";"i"))')
  has_ml=$(cat "$tmp_body_assert" | jq -r '((.structured.applied_filters // []) | tostring | test("Machine Learning";"i"))')
  if [ "$is_table" != "true" ] || [ "$has_grilld" != "true" ] || [ "$has_ml" != "true" ]; then
    echo "ASSERTION_FAILED: expected candidate_table with applied_filters containing Grilld + Machine Learning"
    exit 1
  else
    echo "ASSERTION_PASSED"
  fi
fi
rm -f "$tmp_body_assert"

# 8) Project + certification conjunction
echo "\n=== 8) grilld project AND ML certifications ==="
tmp_body_assert="$(mktemp -t chat_body.XXXXXX)"
http_code=$(curl -sS -o "$tmp_body_assert" -w "%{http_code}" \
  -H "Content-Type: application/json" \
  -X POST \
  --data '{"message":"candidates who have worked on grilld project and have machine learning certifications","session_id":"'$SESSION_ID'"}' \
  "$CHAT_URL")
echo "HTTP_STATUS=$http_code"

if command -v jq >/dev/null 2>&1; then
  cat "$tmp_body_assert" | jq '{session_id, structured_type: (.structured.type // null), applied_filters: (.structured.applied_filters // []), warnings: (.structured.warnings // [])}'
  is_table=$(cat "$tmp_body_assert" | jq -r '(.structured.type // "") == "candidate_table"')
  has_proj=$(cat "$tmp_body_assert" | jq -r '((.structured.applied_filters // []) | tostring | test("grilld";"i"))')
  has_ml=$(cat "$tmp_body_assert" | jq -r '((.structured.applied_filters // []) | tostring | test("machine learning";"i"))')
  if [ "$is_table" != "true" ] || [ "$has_proj" != "true" ] || [ "$has_ml" != "true" ]; then
    echo "ASSERTION_FAILED: expected candidate_table with applied_filters containing both grilld and machine learning"
    exit 1
  else
    echo "ASSERTION_PASSED"
  fi
else
  head -c 2000 "$tmp_body_assert"; echo
fi
rm -f "$tmp_body_assert"
