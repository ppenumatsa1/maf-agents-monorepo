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

if command -v az >/dev/null 2>&1; then
  APP_INSIGHTS_RESOURCE_ID="${APPLICATIONINSIGHTS_RESOURCE_ID:-}"
  if [ -z "$APP_INSIGHTS_RESOURCE_ID" ] && [ -n "${AZURE_RESOURCE_GROUP:-}" ]; then
    APP_INSIGHTS_RESOURCE_ID=$(az resource list \
      -g "$AZURE_RESOURCE_GROUP" \
      --resource-type "microsoft.insights/components" \
      --query "[0].id" -o tsv 2>/dev/null || true)
  fi

  if [ -n "$APP_INSIGHTS_RESOURCE_ID" ]; then
    APP_INSIGHTS_NAME="${APP_INSIGHTS_RESOURCE_ID##*/}"
    APP_INSIGHTS_CONNECTION_STRING=$(az monitor app-insights component show \
      -g "$AZURE_RESOURCE_GROUP" \
      -a "$APP_INSIGHTS_NAME" \
      --query "connectionString" -o tsv 2>/dev/null || true)

    echo "Persisting Application Insights values to azd env."
    azd env set APPLICATIONINSIGHTS_RESOURCE_ID "$APP_INSIGHTS_RESOURCE_ID"
    if [ -n "$APP_INSIGHTS_CONNECTION_STRING" ]; then
      azd env set APPLICATIONINSIGHTS_CONNECTION_STRING "$APP_INSIGHTS_CONNECTION_STRING"
    fi
  else
    echo "Application Insights resource not found; skipping App Insights env sync."
  fi
fi

echo "Writing agent .env from azd values."
cat > "$AGENT_ENV_FILE" <<EOF
FOUNDRY_PROJECTS_ENDPOINT="${FOUNDRY_PROJECTS_ENDPOINT:-}"
FOUNDRY_MODEL_DEPLOYMENT_NAME="${FOUNDRY_MODEL_DEPLOYMENT_NAME:-}"
REQUIRE_AUTH="${REQUIRE_AUTH:-false}"
ENTRA_TENANT_ID="${ENTRA_TENANT_ID:-}"
ENTRA_CLIENT_ID="${ENTRA_CLIENT_ID:-}"
ENTRA_AUDIENCE="${ENTRA_AUDIENCE:-}"
ENTRA_API_AUDIENCE="${ENTRA_API_AUDIENCE:-${ENTRA_AUDIENCE:-}}"
ENTRA_SCOPE="${ENTRA_SCOPE:-}"
ENTRA_AUTHORITY="${ENTRA_AUTHORITY:-}"
ENTRA_ISSUER="${ENTRA_ISSUER:-}"
ENTRA_JWKS_URL="${ENTRA_JWKS_URL:-}"
ENTRA_JWKS_CACHE_TTL_SECONDS="${ENTRA_JWKS_CACHE_TTL_SECONDS:-300}"
EOF

if command -v azd >/dev/null 2>&1; then
  echo "Setting azd env values from .env"
  azd env set FOUNDRY_PROJECTS_ENDPOINT "${FOUNDRY_PROJECTS_ENDPOINT:-}"
  azd env set FOUNDRY_MODEL_DEPLOYMENT_NAME "${FOUNDRY_MODEL_DEPLOYMENT_NAME:-}"
  azd env set REQUIRE_AUTH "${REQUIRE_AUTH:-false}"
  azd env set ENTRA_TENANT_ID "${ENTRA_TENANT_ID:-}"
  azd env set ENTRA_CLIENT_ID "${ENTRA_CLIENT_ID:-}"
  azd env set ENTRA_AUDIENCE "${ENTRA_AUDIENCE:-}"
  azd env set ENTRA_API_AUDIENCE "${ENTRA_API_AUDIENCE:-${ENTRA_AUDIENCE:-}}"
  azd env set ENTRA_SCOPE "${ENTRA_SCOPE:-}"
  azd env set ENTRA_AUTHORITY "${ENTRA_AUTHORITY:-}"
  azd env set ENTRA_ISSUER "${ENTRA_ISSUER:-}"
  azd env set ENTRA_JWKS_URL "${ENTRA_JWKS_URL:-}"
  azd env set ENTRA_JWKS_CACHE_TTL_SECONDS "${ENTRA_JWKS_CACHE_TTL_SECONDS:-300}"
fi
