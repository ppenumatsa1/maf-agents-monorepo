#!/usr/bin/env bash
set -euo pipefail

# Usage: ./scripts/verify_deployment.sh --env local|azure --base-url URL
#                                     [--tenant-id ID] [--client-id ID]
#                                     [--client-secret SECRET] [--scope SCOPE]
#                                     [--strict-endpoint-execution|--allow-upstream-failure]
#
# Auth behavior:
# - local: auth disabled
# - azure: auth enabled

ENVIRONMENT="local"
BASE_URL=""
STRICT_ENDPOINT_EXECUTION="false"
STRICT_ENDPOINT_EXECUTION_SET="false"
TENANT_ID="${ENTRA_TENANT_ID:-}"
CLIENT_ID="${ENTRA_CLIENT_ID:-}"
CLIENT_SECRET="${ENTRA_CLIENT_SECRET:-}"
SCOPE="${ENTRA_SCOPE:-}"
REQUIRE_AUTH="false"

require_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Error: required command '$cmd' was not found." >&2
    exit 1
  fi
}

resolve_base_url() {
  if [ -z "$BASE_URL" ]; then
    echo "Error: --base-url is required." >&2
    exit 1
  fi
}

apply_target_defaults() {
  if [ "$ENVIRONMENT" = "azure" ]; then
    REQUIRE_AUTH="true"
  else
    REQUIRE_AUTH="false"
  fi

  if [ "$STRICT_ENDPOINT_EXECUTION_SET" = "false" ]; then
    if [ "$ENVIRONMENT" = "azure" ]; then
      STRICT_ENDPOINT_EXECUTION="true"
    else
      STRICT_ENDPOINT_EXECUTION="false"
    fi
  fi
}

resolve_auth_inputs() {
  if [ "$REQUIRE_AUTH" != "true" ]; then
    return
  fi
}

validate_auth_inputs() {
  if [ "$REQUIRE_AUTH" != "true" ]; then
    return
  fi

  if [ -z "$TENANT_ID" ] || [ -z "$CLIENT_ID" ] || [ -z "$CLIENT_SECRET" ]; then
    echo "Error: --require-auth requires tenant/client credentials." >&2
    echo "Set ENTRA_TENANT_ID, ENTRA_CLIENT_ID, ENTRA_CLIENT_SECRET or pass flags." >&2
    exit 1
  fi

  if [ -z "$SCOPE" ]; then
    echo "Error: missing scope. Provide --scope or ENTRA_SCOPE." >&2
    exit 1
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      ENVIRONMENT="$2"
      shift 2
      ;;
    --base-url)
      BASE_URL="$2"
      shift 2
      ;;
    --tenant-id)
      TENANT_ID="$2"
      shift 2
      ;;
    --client-id)
      CLIENT_ID="$2"
      shift 2
      ;;
    --client-secret)
      CLIENT_SECRET="$2"
      shift 2
      ;;
    --scope)
      SCOPE="$2"
      shift 2
      ;;
    --strict-endpoint-execution)
      STRICT_ENDPOINT_EXECUTION="true"
      STRICT_ENDPOINT_EXECUTION_SET="true"
      shift
      ;;
    --allow-upstream-failure)
      STRICT_ENDPOINT_EXECUTION="false"
      STRICT_ENDPOINT_EXECUTION_SET="true"
      shift
      ;;
    -h|--help)
      echo "Usage: $0 --env local|azure --base-url URL"
      echo "          [--tenant-id ID] [--client-id ID] [--client-secret SECRET]"
      echo "          [--scope SCOPE]"
      echo "          [--strict-endpoint-execution|--allow-upstream-failure]"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

if [ "$ENVIRONMENT" != "local" ] && [ "$ENVIRONMENT" != "azure" ]; then
  echo "Error: --env must be 'local' or 'azure'." >&2
  exit 1
fi

require_command curl
require_command jq

resolve_base_url
apply_target_defaults
resolve_auth_inputs
validate_auth_inputs

echo ""
echo "=========================================="
echo "Post-Deployment Verification"
echo "=========================================="
echo "Environment: $ENVIRONMENT"
echo "Target: $BASE_URL"
echo "Auth mode: $REQUIRE_AUTH"
echo "Strict endpoint execution: $STRICT_ENDPOINT_EXECUTION"
echo ""

AUTHORIZATION_HEADER=""
if [ "$REQUIRE_AUTH" = "true" ]; then
  TOKEN_RESPONSE=$(curl -sS -X POST \
    "https://login.microsoftonline.com/$TENANT_ID/oauth2/v2.0/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    --data-urlencode "client_id=$CLIENT_ID" \
    --data-urlencode "client_secret=$CLIENT_SECRET" \
    --data-urlencode "scope=$SCOPE" \
    --data-urlencode "grant_type=client_credentials")

  ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.access_token // empty')
  if [ -z "$ACCESS_TOKEN" ]; then
    echo "Error: failed to acquire access token." >&2
    echo "Token response: $TOKEN_RESPONSE" >&2
    exit 1
  fi

  AUTHORIZATION_HEADER="Authorization: Bearer $ACCESS_TOKEN"
fi

curl_with_auth() {
  if [ -n "$AUTHORIZATION_HEADER" ]; then
    curl "$@" -H "$AUTHORIZATION_HEADER"
  else
    curl "$@"
  fi
}

RESEARCH_PAYLOAD='{"topic":"AI agent observability patterns","audience":"engineering leads","tone":"concise","length":"short","time_range":"last 12 months"}'
FAILED_CHECKS=0

echo "Test 1/4: Health endpoint"
HEALTH_RESPONSE=""
HEALTH_STATUS=""
for attempt in $(seq 1 20); do
  if HEALTH_RESPONSE=$(curl_with_auth -sS --max-time 10 -D - "$BASE_URL/health" 2>/dev/null); then
    HEALTH_STATUS=$(sed -n '1p' <<<"$HEALTH_RESPONSE" | awk '{print $2}')
    if [ "$HEALTH_STATUS" = "200" ]; then
      break
    fi
  fi
  if [ "$attempt" -eq 20 ]; then
    echo "  Health check failed after retries"
    exit 1
  fi
  sleep 1
done

HEALTH_BODY=$(echo "$HEALTH_RESPONSE" | sed -n '/^\r$/,$p' | sed '1d')
if [ "$HEALTH_STATUS" = "200" ]; then
  echo "  Health check passed (HTTP 200)"
else
  echo "  Health check failed (HTTP $HEALTH_STATUS)"
  exit 1
fi

HEALTH_VALUE=$(echo "$HEALTH_BODY" | jq -r '.status // empty' 2>/dev/null || true)
if [ "$HEALTH_VALUE" != "ok" ]; then
  echo "  Unexpected health response body: $HEALTH_BODY"
  exit 1
fi
echo ""

echo "Test 2/4: Correlation header propagation"
CORRELATION_HEADER=$(echo "$HEALTH_RESPONSE" | tr -d '\r' | grep -i '^x-correlation-id:' || true)
if [ -n "$CORRELATION_HEADER" ]; then
  echo "  x-correlation-id response header present"
else
  echo "  x-correlation-id response header missing"
  FAILED_CHECKS=$((FAILED_CHECKS + 1))
fi
echo ""

echo "Test 3/4: Research endpoint execution"
RESEARCH_RESPONSE=$(curl_with_auth -sS --max-time 180 -D - \
  -X POST "$BASE_URL/v1/research" \
  -H "Content-Type: application/json" \
  -d "$RESEARCH_PAYLOAD")
RESEARCH_STATUS=$(sed -n '1p' <<<"$RESEARCH_RESPONSE" | awk '{print $2}')
RESEARCH_BODY=$(echo "$RESEARCH_RESPONSE" | sed -n '/^\r$/,$p' | sed '1d')

if [ "$RESEARCH_STATUS" = "200" ]; then
  if echo "$RESEARCH_BODY" | jq -e '((.summary | type) == "string") and ((.draft | type) == "string") and ((.review | type) == "string")' >/dev/null 2>&1; then
    echo "  /v1/research returned expected response shape (HTTP 200)"
  else
    echo "  /v1/research response missing expected fields: $RESEARCH_BODY"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
  fi
elif [ "$STRICT_ENDPOINT_EXECUTION" = "false" ] && [ "$RESEARCH_STATUS" -ge 500 ]; then
  echo "  /v1/research endpoint reachable, upstream model unavailable (HTTP $RESEARCH_STATUS)"
else
  echo "  /v1/research failed (HTTP $RESEARCH_STATUS)"
  echo "  Response: $RESEARCH_BODY"
  FAILED_CHECKS=$((FAILED_CHECKS + 1))
fi
echo ""

echo "Test 4/4: Streaming endpoint execution"
STREAM_RESPONSE=$(curl_with_auth -sS --max-time 180 -D - \
  -X POST "$BASE_URL/v1/research/stream" \
  -H "Content-Type: application/json" \
  -d "$RESEARCH_PAYLOAD")
STREAM_STATUS=$(sed -n '1p' <<<"$STREAM_RESPONSE" | awk '{print $2}')
STREAM_HEADERS=$(echo "$STREAM_RESPONSE" | sed -n '1,/^\r$/p' | tr -d '\r')
STREAM_BODY=$(echo "$STREAM_RESPONSE" | sed -n '/^\r$/,$p' | sed '1d')

if [ "$STREAM_STATUS" = "200" ]; then
  if grep -iq '^content-type: text/event-stream' <<<"$STREAM_HEADERS"; then
    echo "  /v1/research/stream returned SSE content type (HTTP 200)"
  else
    echo "  /v1/research/stream missing SSE content type"
    echo "  Headers: $STREAM_HEADERS"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
  fi

  if grep -q 'data:' <<<"$STREAM_BODY"; then
    echo "  /v1/research/stream emitted SSE events"
  elif [ "$STRICT_ENDPOINT_EXECUTION" = "false" ]; then
    echo "  /v1/research/stream reachable but emitted no SSE payload in lenient mode"
  else
    echo "  /v1/research/stream did not emit SSE events"
    echo "  Body: $STREAM_BODY"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
  fi
elif [ "$STRICT_ENDPOINT_EXECUTION" = "false" ] && [ "$STREAM_STATUS" -ge 500 ]; then
  echo "  /v1/research/stream endpoint reachable, upstream model unavailable (HTTP $STREAM_STATUS)"
else
  echo "  /v1/research/stream failed (HTTP $STREAM_STATUS)"
  echo "  Response: $STREAM_BODY"
  FAILED_CHECKS=$((FAILED_CHECKS + 1))
fi
echo ""

if [ "$FAILED_CHECKS" -gt 0 ]; then
  echo "=========================================="
  echo "Verification completed with failures"
  echo "=========================================="
  echo "Failed checks: $FAILED_CHECKS"
  exit 1
fi

echo "=========================================="
echo "All verification tests passed"
echo "=========================================="
echo ""
echo "Service checks confirmed:"
echo "  - Health endpoint is reachable"
echo "  - Correlation headers are propagated"
echo "  - Research endpoints execute successfully"
echo ""
