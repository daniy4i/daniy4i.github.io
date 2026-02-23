#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
FRONTEND_URL="${2:-http://localhost:3000}"

if ! curl -fsS "$BASE_URL/health" >/dev/null 2>&1; then
  echo "❌ Backend is not reachable at $BASE_URL. Start the stack first: make do-it-all"
  exit 1
fi
echo "✅ Backend healthy"

if ! curl -fsS "$FRONTEND_URL" >/dev/null 2>&1; then
  echo "❌ Frontend is not reachable at $FRONTEND_URL. Start the stack first: make do-it-all"
  exit 1
fi
echo "✅ Frontend reachable"

LOGIN_RESPONSE=$(curl -fsS -X POST "$BASE_URL/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin"}')

TOKEN=$(printf '%s' "$LOGIN_RESPONSE" | python -c 'import sys,json;
try:
 d=json.load(sys.stdin); print(d.get("access_token",""))
except Exception:
 print("")')

if [ -z "$TOKEN" ]; then
  echo "❌ Auth endpoint did not return a token"
  exit 1
fi
echo "✅ Auth working"

curl -fsS "$BASE_URL/api/jobs" -H "Authorization: Bearer $TOKEN" >/dev/null

echo "✅ Jobs endpoint working"
echo "🎉 All core checks passed"
