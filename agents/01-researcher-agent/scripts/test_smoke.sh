#!/usr/bin/env bash
set -euo pipefail

HOST="127.0.0.1"
PORT="${SMOKE_PORT:-18000}"
BASE_URL="http://${HOST}:${PORT}"
LOG_FILE="${SMOKE_SERVER_LOG:-/tmp/01-researcher-agent-smoke.log}"

export REQUIRE_AUTH=false

python3 -m uvicorn app.main:create_app --host "$HOST" --port "$PORT" >"$LOG_FILE" 2>&1 &
SERVER_PID=$!

cleanup() {
  if kill -0 "$SERVER_PID" >/dev/null 2>&1; then
    kill "$SERVER_PID" >/dev/null 2>&1 || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT

for _ in $(seq 1 40); do
  if curl -fsS --max-time 2 "${BASE_URL}/health" >/dev/null 2>&1; then
    bash ./scripts/verify_deployment.sh --env local --base-url "$BASE_URL"
    exit 0
  fi
  sleep 1
done

echo "Smoke server failed to become healthy at ${BASE_URL}." >&2
echo "Server log (${LOG_FILE}):" >&2
tail -n 100 "$LOG_FILE" >&2 || true
exit 1
