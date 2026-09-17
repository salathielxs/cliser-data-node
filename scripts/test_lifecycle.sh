#!/data/data/com.termux/files/usr/bin/bash

set -u

BASE="http://127.0.0.1:8080"

echo "== CLISER DATA NODE / LIFECYCLE TEST =="

if [ -z "${CLISER_TOKEN:-}" ]; then
    echo "ERRO: CLISER_TOKEN não está definido."
    exit 1
fi

echo "[1/4] Authentication..."

CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $CLISER_TOKEN" \
    "$BASE/api/v1/metrics")

if [ "$CODE" != "200" ]; then
    echo "FALHA: autenticação."
    echo "HTTP=$CODE"
    exit 1
fi

echo "OK"

echo "[2/4] Integrity check..."

curl -s \
    -X POST \
    -H "Authorization: Bearer $CLISER_TOKEN" \
    "$BASE/api/v1/lifecycle/integrity-check" \
    | jq

echo

echo "[3/4] Rebuild refcounts..."

curl -s \
    -X POST \
    -H "Authorization: Bearer $CLISER_TOKEN" \
    "$BASE/api/v1/lifecycle/rebuild-refcounts" \
    | jq

echo

echo "[4/4] Final integrity check..."

curl -s \
    -X POST \
    -H "Authorization: Bearer $CLISER_TOKEN" \
    "$BASE/api/v1/lifecycle/integrity-check" \
    | jq

echo
echo "== TESTE CONCLUÍDO =="
