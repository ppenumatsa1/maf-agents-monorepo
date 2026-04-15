#!/usr/bin/env sh
set -e
set -x

echo "Predeploy hook: build and push researcher-agent image."

ROOT_DIR=$(cd "$(dirname "$0")/../.." && pwd)

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

AZD_ENV_FILE="$ROOT_DIR/.azure/${AZURE_ENV_NAME}/.env"
if [ -f "$AZD_ENV_FILE" ]; then
  echo "Loading azd .env overrides..."
  set -a
  # shellcheck disable=SC1090
  . "$AZD_ENV_FILE"
  set +a
fi

REQUIRE_AUTH_VALUE="${REQUIRE_AUTH:-false}"
ENTRA_AUTHORITY_VALUE="${ENTRA_AUTHORITY:-}"
ENTRA_JWKS_CACHE_TTL_VALUE="${ENTRA_JWKS_CACHE_TTL_SECONDS:-300}"
ENTRA_ISSUER_VALUE="${ENTRA_ISSUER:-}"
ENTRA_JWKS_URL_VALUE="${ENTRA_JWKS_URL:-}"
ENTRA_AUDIENCE_VALUE="${ENTRA_AUDIENCE:-${ENTRA_CLIENT_ID:-}}"
ENTRA_SCOPE_VALUE="${ENTRA_SCOPE:-}"

if [ -z "$ENTRA_AUTHORITY_VALUE" ] && [ -n "${ENTRA_TENANT_ID:-}" ]; then
  ENTRA_AUTHORITY_VALUE="https://login.microsoftonline.com/${ENTRA_TENANT_ID}"
fi

if [ -z "$ENTRA_ISSUER_VALUE" ] && [ -n "${ENTRA_TENANT_ID:-}" ]; then
  ENTRA_ISSUER_VALUE="https://sts.windows.net/${ENTRA_TENANT_ID}/"
fi

if [ -z "$ENTRA_JWKS_URL_VALUE" ] && [ -n "$ENTRA_AUTHORITY_VALUE" ]; then
  ENTRA_JWKS_URL_VALUE="${ENTRA_AUTHORITY_VALUE}/discovery/v2.0/keys"
fi

if [ -z "${FOUNDRY_PROJECTS_ENDPOINT:-}" ] || [ -z "${FOUNDRY_MODEL_DEPLOYMENT_NAME:-}" ]; then
  echo "Missing FOUNDRY_PROJECTS_ENDPOINT or FOUNDRY_MODEL_DEPLOYMENT_NAME in azd environment."
  exit 1
fi

if [ "$REQUIRE_AUTH_VALUE" = "true" ] || [ "$REQUIRE_AUTH_VALUE" = "1" ]; then
  MISSING_AUTH_VARS=""
  [ -n "${ENTRA_TENANT_ID:-}" ] || MISSING_AUTH_VARS="$MISSING_AUTH_VARS ENTRA_TENANT_ID"
  [ -n "${ENTRA_CLIENT_ID:-}" ] || MISSING_AUTH_VARS="$MISSING_AUTH_VARS ENTRA_CLIENT_ID"
  [ -n "$ENTRA_AUDIENCE_VALUE" ] || MISSING_AUTH_VARS="$MISSING_AUTH_VARS ENTRA_AUDIENCE"
  [ -n "$ENTRA_SCOPE_VALUE" ] || MISSING_AUTH_VARS="$MISSING_AUTH_VARS ENTRA_SCOPE"
  [ -n "$ENTRA_ISSUER_VALUE" ] || MISSING_AUTH_VARS="$MISSING_AUTH_VARS ENTRA_ISSUER"
  [ -n "$ENTRA_JWKS_URL_VALUE" ] || MISSING_AUTH_VARS="$MISSING_AUTH_VARS ENTRA_JWKS_URL"
  if [ -n "$MISSING_AUTH_VARS" ]; then
    echo "REQUIRE_AUTH=true but missing auth settings:$MISSING_AUTH_VARS"
    echo "Set missing values in azd env before deploy (azd env set <KEY> <VALUE>)."
    exit 1
  fi
fi

echo "Syncing auth/foundry values to azd env."
azd env set REQUIRE_AUTH "$REQUIRE_AUTH_VALUE"
azd env set ENTRA_TENANT_ID "${ENTRA_TENANT_ID:-}"
azd env set ENTRA_CLIENT_ID "${ENTRA_CLIENT_ID:-}"
azd env set ENTRA_AUDIENCE "$ENTRA_AUDIENCE_VALUE"
azd env set ENTRA_API_AUDIENCE "$ENTRA_AUDIENCE_VALUE"
azd env set ENTRA_SCOPE "$ENTRA_SCOPE_VALUE"
azd env set ENTRA_AUTHORITY "$ENTRA_AUTHORITY_VALUE"
azd env set ENTRA_ISSUER "$ENTRA_ISSUER_VALUE"
azd env set ENTRA_JWKS_URL "$ENTRA_JWKS_URL_VALUE"
azd env set ENTRA_JWKS_CACHE_TTL_SECONDS "$ENTRA_JWKS_CACHE_TTL_VALUE"
azd env set FOUNDRY_PROJECTS_ENDPOINT "${FOUNDRY_PROJECTS_ENDPOINT}"
azd env set FOUNDRY_MODEL_DEPLOYMENT_NAME "${FOUNDRY_MODEL_DEPLOYMENT_NAME}"

if [ -n "${AZURE_RESOURCE_GROUP:-}" ] && command -v az >/dev/null 2>&1; then
  CONTAINER_APP_NAME=$(az containerapp list -g "$AZURE_RESOURCE_GROUP" --query "[0].name" -o tsv || true)
  if [ -n "$CONTAINER_APP_NAME" ]; then
    echo "Updating container app env vars for $CONTAINER_APP_NAME"
    az containerapp update -g "$AZURE_RESOURCE_GROUP" -n "$CONTAINER_APP_NAME" \
      --set-env-vars \
        REQUIRE_AUTH="$REQUIRE_AUTH_VALUE" \
        ENTRA_TENANT_ID="${ENTRA_TENANT_ID:-}" \
        ENTRA_CLIENT_ID="${ENTRA_CLIENT_ID:-}" \
        ENTRA_AUDIENCE="$ENTRA_AUDIENCE_VALUE" \
        ENTRA_API_AUDIENCE="$ENTRA_AUDIENCE_VALUE" \
        ENTRA_SCOPE="$ENTRA_SCOPE_VALUE" \
        ENTRA_AUTHORITY="$ENTRA_AUTHORITY_VALUE" \
        ENTRA_ISSUER="$ENTRA_ISSUER_VALUE" \
        ENTRA_JWKS_URL="$ENTRA_JWKS_URL_VALUE" \
        ENTRA_JWKS_CACHE_TTL_SECONDS="$ENTRA_JWKS_CACHE_TTL_VALUE" \
        FOUNDRY_PROJECTS_ENDPOINT="${FOUNDRY_PROJECTS_ENDPOINT}" \
        FOUNDRY_MODEL_DEPLOYMENT_NAME="${FOUNDRY_MODEL_DEPLOYMENT_NAME}"
  fi
fi

if [ -z "$acrLoginServer" ]; then
  echo "acrLoginServer not set; cannot build/push image."
  exit 1
fi

IMAGE_TAG="${acrLoginServer}/researcher-agent:latest"

echo "Logging into ACR: ${acrLoginServer%%.*}"
az acr login --name "${acrLoginServer%%.*}"

echo "Building image: $IMAGE_TAG"
docker build -t "$IMAGE_TAG" "$ROOT_DIR/agents/01-researcher-agent"

echo "Pushing image: $IMAGE_TAG"
docker push "$IMAGE_TAG"

echo "Setting azd env overrides for image and port"
azd env set containerImage "$IMAGE_TAG"
azd env set containerTargetPort "8000"

echo "Built and pushed $IMAGE_TAG"
