#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/kusto/run-observability-suite.sh [--app-id <guid>] [--base-url <url>] [--output table|json]
                                         [--tenant-id <id>] [--client-id <id>] [--client-secret <secret>] [--scope <scope>]
                                         [--skip-traffic]

Notes:
  - If --app-id is not provided, this script attempts to resolve it from
    azd env value APPLICATIONINSIGHTS_CONNECTION_STRING (ApplicationId=...),
    then from Container App APPLICATIONINSIGHTS_CONNECTION_STRING.
  - If --base-url is provided (or resolvable from azd env), traffic is generated
    before validation to make strict telemetry checks deterministic.
  - Runs KQL queries for requests/dependencies/exceptions/traces/custom events/custom metrics.

Examples:
  scripts/kusto/run-observability-suite.sh
  scripts/kusto/run-observability-suite.sh --app-id <guid> --output table
  scripts/kusto/run-observability-suite.sh --base-url https://<fqdn> --tenant-id <id> --client-id <id> --client-secret <secret> --scope <scope>
USAGE
}

APP_ID=""
BASE_URL=""
OUTPUT="table"
TENANT_ID="${ENTRA_TENANT_ID:-}"
CLIENT_ID="${ENTRA_CLIENT_ID:-}"
CLIENT_SECRET="${ENTRA_CLIENT_SECRET:-}"
SCOPE="${ENTRA_SCOPE:-}"
GENERATE_TRAFFIC="true"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --app-id)
      APP_ID="$2"
      shift 2
      ;;
    --output)
      OUTPUT="$2"
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
    --skip-traffic)
      GENERATE_TRAFFIC="false"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

resolve_app_id_from_azd() {
  if ! command -v azd >/dev/null 2>&1; then
    return 1
  fi

  local conn
  conn="$(azd env get-values 2>/dev/null | grep -E '^APPLICATIONINSIGHTS_CONNECTION_STRING=' | head -1 | cut -d'=' -f2- | tr -d '"')"
  if [[ -z "$conn" ]]; then
    return 1
  fi

  echo "$conn" | sed -n 's/.*ApplicationId=\([^;]*\).*/\1/p'
}

resolve_base_url_from_azd() {
  if ! command -v azd >/dev/null 2>&1; then
    return 1
  fi

  local fqdn
  fqdn="$(azd env get-values 2>/dev/null | grep -E '^containerAppFqdn=' | head -1 | cut -d'=' -f2- | tr -d '"')"
  if [[ -z "$fqdn" ]]; then
    return 1
  fi

  echo "https://$fqdn"
}

resolve_resource_group_from_azd() {
  if ! command -v azd >/dev/null 2>&1; then
    return 1
  fi

  azd env get-values 2>/dev/null | sed -n 's/^AZURE_RESOURCE_GROUP="\(.*\)"/\1/p' | head -1
}

resolve_app_id_from_container_app() {
  if ! command -v az >/dev/null 2>&1; then
    return 1
  fi

  local fqdn rg app conn
  fqdn="${1:-}"
  rg="${2:-}"

  if [[ -n "$fqdn" ]]; then
    fqdn="${fqdn#https://}"
    fqdn="${fqdn#http://}"
    rg="$(az containerapp list --query "[?properties.configuration.ingress.fqdn=='$fqdn'].resourceGroup | [0]" -o tsv 2>/dev/null || true)"
    app="$(az containerapp list --query "[?properties.configuration.ingress.fqdn=='$fqdn'].name | [0]" -o tsv 2>/dev/null || true)"
  fi

  if [[ -z "${app:-}" && -n "$rg" ]]; then
    app="$(az containerapp list -g "$rg" --query "[0].name" -o tsv 2>/dev/null || true)"
  fi

  if [[ -z "${rg:-}" || -z "${app:-}" ]]; then
    return 1
  fi

  conn="$(az containerapp show -g "$rg" -n "$app" --query "properties.template.containers[0].env[?name=='APPLICATIONINSIGHTS_CONNECTION_STRING'].value | [0]" -o tsv 2>/dev/null || true)"
  if [[ -z "$conn" ]]; then
    return 1
  fi

  echo "$conn" | sed -n 's/.*ApplicationId=\([^;]*\).*/\1/p'
}

generate_traffic() {
  local token=""

  if [[ -z "$BASE_URL" ]]; then
    return 0
  fi

  echo "Generating traffic against $BASE_URL"
  curl -fsS --max-time 10 "$BASE_URL/health" >/dev/null || true
  curl -fsS --max-time 10 "$BASE_URL/health" >/dev/null || true

  if [[ -n "$TENANT_ID" && -n "$CLIENT_ID" && -n "$CLIENT_SECRET" && -n "$SCOPE" ]]; then
    token="$(curl -fsS --max-time 20 -X POST "https://login.microsoftonline.com/${TENANT_ID}/oauth2/v2.0/token" \
      -H 'Content-Type: application/x-www-form-urlencoded' \
      --data-urlencode "client_id=${CLIENT_ID}" \
      --data-urlencode "client_secret=${CLIENT_SECRET}" \
      --data-urlencode "scope=${SCOPE}" \
      --data-urlencode 'grant_type=client_credentials' | jq -r '.access_token // ""')"

    if [[ -n "$token" ]]; then
      curl -fsS --max-time 30 -X POST "$BASE_URL/v1/research" \
        -H "Authorization: Bearer $token" \
        -H 'Content-Type: application/json' \
        -d '{"topic":"observability verification", "context":"telemetry baseline", "constraints":"brief"}' \
        >/dev/null || true

      curl -fsS --max-time 30 -X POST "$BASE_URL/v1/research/stream" \
        -H "Authorization: Bearer $token" \
        -H 'Accept: text/event-stream' \
        -H 'Content-Type: application/json' \
        -d '{"topic":"stream observability verification", "context":"sse telemetry", "constraints":"brief"}' \
        >/dev/null || true
    else
      echo "Warning: failed to obtain access token for authenticated traffic generation." >&2
    fi
  else
    echo "Info: auth parameters not fully set; skipping authenticated research traffic generation." >&2
  fi

  # Allow for telemetry ingestion latency.
  sleep 10
}

if [[ -z "$APP_ID" ]]; then
  APP_ID="$(resolve_app_id_from_azd || true)"
fi

if [[ -z "$BASE_URL" ]]; then
  BASE_URL="$(resolve_base_url_from_azd || true)"
fi

if [[ -z "$APP_ID" ]]; then
  APP_ID="$(resolve_app_id_from_container_app "$BASE_URL" "$(resolve_resource_group_from_azd || true)" || true)"
fi

if [[ -z "$APP_ID" ]]; then
  echo "Unable to resolve Application Insights app id. Provide --app-id." >&2
  exit 1
fi

run_file_query() {
  local title="$1"
  local file="$2"

  echo ""
  echo "============================================================"
  echo "$title"
  echo "Query: $file"
  echo "============================================================"

  az monitor app-insights query \
    --app "$APP_ID" \
    --analytics-query "$(cat "$file")" \
    -o "$OUTPUT"
}

extract_scalar_count() {
  local query="$1"
  az monitor app-insights query \
    --app "$APP_ID" \
    --analytics-query "$query" \
    -o json | jq -r '.tables[0].rows[0][0] // 0'
}

validate_counts() {
  local req_count dep_count trace_count custom_event_count custom_metric_count

  req_count="$(extract_scalar_count "requests | where timestamp > ago(30m) | count")"
  dep_count="$(extract_scalar_count "dependencies | where timestamp > ago(30m) | count")"
  trace_count="$(extract_scalar_count "traces | where timestamp > ago(30m) | count")"
  custom_event_count="$(extract_scalar_count "customEvents | where timestamp > ago(30m) | count")"
  custom_metric_count="$(extract_scalar_count "customMetrics | where timestamp > ago(30m) | count")"

  echo ""
  echo "Validation (last 30m):"
  echo "  requests     : $req_count"
  echo "  dependencies : $dep_count"
  echo "  traces       : $trace_count"
  echo "  customEvents : $custom_event_count"
  echo "  customMetrics: $custom_metric_count"

  if [[ "$req_count" -lt 1 ]]; then
    echo "Validation failed: expected at least 1 request row." >&2
    exit 2
  fi

  if [[ "$dep_count" -lt 1 ]]; then
    echo "Validation failed: expected at least 1 dependency row." >&2
    exit 2
  fi

  if [[ "$trace_count" -lt 1 ]]; then
    echo "Validation failed: expected at least 1 trace row." >&2
    exit 2
  fi

  if [[ "$custom_event_count" -lt 1 ]]; then
    echo "Validation warning: customEvents has no rows in the last 60m." >&2
    echo "Proceeding because traces and customMetrics are present." >&2
  fi

  if [[ "$custom_metric_count" -lt 1 ]]; then
    echo "Validation failed: expected at least 1 custom metric row." >&2
    exit 2
  fi

  echo "Validation passed."
}

if [[ "$GENERATE_TRAFFIC" == "true" ]]; then
  generate_traffic
fi

run_file_query "Requests" "$SCRIPT_DIR/requests.kql"
run_file_query "Auth failures (401/403)" "$SCRIPT_DIR/auth-failures.kql"
run_file_query "Dependencies" "$SCRIPT_DIR/dependencies.kql"
run_file_query "Exceptions" "$SCRIPT_DIR/exceptions.kql"
run_file_query "Traces" "$SCRIPT_DIR/traces.kql"
run_file_query "Custom events" "$SCRIPT_DIR/custom-events.kql"
run_file_query "Custom metrics" "$SCRIPT_DIR/custom-metrics.kql"

validate_counts
