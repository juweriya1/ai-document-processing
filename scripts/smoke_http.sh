#!/usr/bin/env bash
# End-to-end HTTP smoke test for the IDP pipeline.
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8000}"
PDF="${PDF:-uploads/doc_468b24dbdb75.pdf}"
EMAIL="smoke_$(date +%s)@example.com"
PASS="StrongPass1!"

echo "==> register $EMAIL"
curl -s -X POST "$BASE/api/auth/register" \
  -H 'content-type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\",\"name\":\"Smoke Tester\",\"role\":\"enterprise_user\"}" | tee /tmp/register.json
echo

echo "==> login"
TOKEN=$(curl -s -X POST "$BASE/api/auth/login" \
  -H 'content-type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" | .venv/bin/python -c "import json,sys;print(json.load(sys.stdin)['access_token'])")
echo "TOKEN=${TOKEN:0:30}..."

echo "==> upload $PDF"
UP=$(curl -s -X POST "$BASE/api/documents/upload" \
  -H "authorization: Bearer $TOKEN" \
  -F "file=@$PDF")
echo "$UP" | tee /tmp/upload.json
DOC_ID=$(echo "$UP" | .venv/bin/python -c "import json,sys;d=json.load(sys.stdin);print(d.get('id') or d.get('document_id'))")
echo "DOC_ID=$DOC_ID"

echo "==> trigger pipeline"
curl -s -X POST "$BASE/api/documents/$DOC_ID/process" \
  -H "authorization: Bearer $TOKEN"
echo

echo "==> poll status"
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
  STATUS=$(curl -s "$BASE/api/documents/$DOC_ID/status" -H "authorization: Bearer $TOKEN")
  STATE=$(echo "$STATUS" | .venv/bin/python -c "import json,sys;print(json.load(sys.stdin).get('status'))")
  echo "  [$i] status=$STATE"
  case "$STATE" in
    verified|review_pending|failed) echo "$STATUS" | tee /tmp/final.json; break ;;
  esac
  sleep 2
done

echo
echo "==> fields"
curl -s "$BASE/api/documents/$DOC_ID/fields" -H "authorization: Bearer $TOKEN" | tee /tmp/fields.json
echo
