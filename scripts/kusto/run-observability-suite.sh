#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/kusto/run-observability-suite.sh [--app-id <guid>] [--output table|json]

Notes:
  - If --app-id is not provided, this script attempts to resolve it from
    azd env value APPLICATIONINSIGHTS_CONNECTION_STRING (ApplicationId=...).
  - Runs KQL queries for requests/dependencies/exceptions/traces/custom events/custom metrics.

Examples:
  scripts/kusto/run-observability-suite.sh
  scripts/kusto/run-observability-suite.sh --app-id <guid> --output table
USAGE
}

APP_ID=""
OUTPUT="table"
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

if [[ -z "$APP_ID" ]]; then
  APP_ID="$(resolve_app_id_from_azd || true)"
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
  custom_event_count="$(extract_scalar_count "customEvents | where timestamp > ago(60m) | count")"
  custom_metric_count="$(extract_scalar_count "customMetrics | where timestamp > ago(60m) | count")"

  echo ""
  echo "Validation (last 30m):"
  echo "  requests     : $req_count"
  echo "  dependencies : $dep_count"
  echo "  traces       : $trace_count"
  echo "  customEvents : $custom_event_count (all names in last 60m)"
  echo "  customMetrics: $custom_metric_count (all names in last 60m)"

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

run_file_query "Requests" "$SCRIPT_DIR/requests.kql"
run_file_query "Auth failures (401/403)" "$SCRIPT_DIR/auth-failures.kql"
run_file_query "Dependencies" "$SCRIPT_DIR/dependencies.kql"
run_file_query "Exceptions" "$SCRIPT_DIR/exceptions.kql"
run_file_query "Traces" "$SCRIPT_DIR/traces.kql"
run_file_query "Custom events" "$SCRIPT_DIR/custom-events.kql"
run_file_query "Custom metrics" "$SCRIPT_DIR/custom-metrics.kql"

validate_counts
