#!/usr/bin/env bash
set -euo pipefail

AGENT="${AGENT:-01-researcher-agent}"
SCRIPT="agents/${AGENT}/scripts/verify_deployment.sh"

if [ ! -f "$SCRIPT" ]; then
  echo "Error: verification script not found for agent '${AGENT}': $SCRIPT" >&2
  echo "Add the script under agents/<agent>/scripts/verify_deployment.sh" >&2
  exit 1
fi

if [ -d "agents/${AGENT}/.venv/bin" ]; then
  export PATH="$(pwd)/agents/${AGENT}/.venv/bin:$PATH"
fi

exec bash "$SCRIPT" "$@"
