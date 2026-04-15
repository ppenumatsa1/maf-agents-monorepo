#!/usr/bin/env bash
set -euo pipefail

AGENT="${AGENT:-01-researcher-agent}"

cd "agents/${AGENT}"
if [ -d ".venv/bin" ]; then
  export PATH="$(pwd)/.venv/bin:$PATH"
fi

./scripts/lint.sh
