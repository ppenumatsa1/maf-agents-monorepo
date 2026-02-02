#!/usr/bin/env sh
set -e
set -x

echo "Postprovision hook: load .env values into azd env."

if command -v azd >/dev/null 2>&1; then
  echo "Loading azd environment values..."
  AZD_ENV_VALUES=$(AZD_DEBUG=0 azd env get-values 2>/dev/null | grep -E '^[A-Za-z_][A-Za-z0-9_]*=')
  if [ -n "$AZD_ENV_VALUES" ]; then
    AZD_ENV_FILE=$(mktemp)
    printf '%s\n' "$AZD_ENV_VALUES" > "$AZD_ENV_FILE"
    # shellcheck disable=SC1090
    . "$AZD_ENV_FILE" || true
    rm -f "$AZD_ENV_FILE"
  fi
fi

ROOT_DIR=$(cd "$(dirname "$0")/../.." && pwd)
AZD_ENV_FILE="$ROOT_DIR/.azure/${AZURE_ENV_NAME}/.env"
AGENT_ENV_FILE="$ROOT_DIR/agents/01-researcher-agent/.env"

if [ ! -f "$AZD_ENV_FILE" ]; then
  echo "No azd .env found; skipping agent sync."
  exit 0
fi

echo "Loading azd .env values."
set -a
# shellcheck disable=SC1090
. "$AZD_ENV_FILE"
set +a

echo "Writing agent .env from azd values."
cat > "$AGENT_ENV_FILE" <<EOF
FOUNDRY_PROJECTS_ENDPOINT="${FOUNDRY_PROJECTS_ENDPOINT}"
FOUNDRY_MODEL_DEPLOYMENT_NAME="${FOUNDRY_MODEL_DEPLOYMENT_NAME}"
EOF

if command -v azd >/dev/null 2>&1; then
  echo "Setting azd env values from .env"
  azd env set FOUNDRY_PROJECTS_ENDPOINT "$FOUNDRY_PROJECTS_ENDPOINT"
  azd env set FOUNDRY_MODEL_DEPLOYMENT_NAME "$FOUNDRY_MODEL_DEPLOYMENT_NAME"
fi
