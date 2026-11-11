#!/usr/bin/env bash
# ContractGuard demo launcher.
#
# Starts the deterministic Giftshop API on 127.0.0.1:8099 and prints the exact
# prompts to paste into Hermes.
#
#   ./demo/run_demo.sh              # broken mode (price is a string) -> FAIL
#   DEMO_BROKEN=0 ./demo/run_demo.sh # fixed mode  (price is a number)  -> PASS
#
# Requirements: Python 3.10+, the repo's dev environment installed
# (pip install -e ".[demo]"), and the ContractGuard plugin enabled in Hermes.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${DEMO_PORT:-8099}"
BROKEN="${DEMO_BROKEN:-1}"
HOST="127.0.0.1"
BASE_URL="http://${HOST}:${PORT}"

cd "$REPO_ROOT"

PYTHON="${PYTHON:-$REPO_ROOT/.venv/bin/python}"
if [ ! -x "$PYTHON" ]; then
  PYTHON="$(command -v python3)"
fi

echo "==> Starting the demo API on ${BASE_URL} (DEMO_BROKEN=${BROKEN})"
DEMO_BROKEN="$BROKEN" "$PYTHON" -m uvicorn demo.app:app --host "$HOST" --port "$PORT" &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT

for _ in $(seq 1 40); do
  if curl -fsS "${BASE_URL}/health" >/dev/null 2>&1; then break; fi
  sleep 0.25
done

echo
echo "    API response:"
curl -fsS "${BASE_URL}/products/p-101" | sed 's/^/    /'
echo
echo "==> ContractGuard is live in Hermes. Paste these prompts in order."
echo
echo "  1) Inspect the contract"
echo "     Use ContractGuard to inspect demo/openapi.yaml and list the operations."
echo
echo "  2) Register the service"
echo "     Use ContractGuard to register a service 'giftshop-api' from demo/openapi.yaml"
echo "     with base URL ${BASE_URL}."
echo
echo "  3) Preflight a bad request (nothing is sent)"
echo "     Use ContractGuard to validate the request body {\"invalid\": \"json\"} against"
echo "     operation createProduct. Do not send it."
echo
echo "  4) Prove the live API violates its contract"
echo "     Use ContractGuard to run the getProduct check with product_id=p-101."
echo
echo "  5) Re-run after the fix (restart the API with DEMO_BROKEN=0)"
echo "     Use ContractGuard to run the getProduct check again."
echo
echo "==> Press Ctrl+C to stop the demo API."
wait "$API_PID"
