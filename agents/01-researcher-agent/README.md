# 01-researcher-agent

Researcher agent built with FastAPI and Microsoft Agent Framework (MAF).

## Architecture

- FastAPI app entrypoint: `app/main.py`
- API routes: `app/api/v1/routers/health.py`, `app/api/v1/routers/research.py`
- Request/response schemas: `app/api/v1/schemas/research.py`
- Research module: `app/modules/research/service.py`
- MAF orchestration: `app/maf/workflows/research_workflow.py`
- MAF prompts: `app/maf/prompts/prompts.py`
- MAF tools (DuckDuckGo web search): `app/maf/tools.py`
- Security/auth dependencies: `app/core/security/*`
- Observability wiring: `app/core/observability/telemetry.py`

## Authentication & RBAC

Auth is controlled by `REQUIRE_AUTH`:

- `REQUIRE_AUTH=false` (default local mode): requests are allowed and treated as anonymous principal.
- `REQUIRE_AUTH=true`: Entra JWT validation is enforced and route RBAC checks are active.

Current route role requirements:

- `POST /v1/research` requires `Research.Read`
- `POST /v1/research/stream` requires `Research.Write`

When auth is enabled, missing/invalid tokens return `401`, and missing required roles return `403`.

## Environment Variables

- `PORT`: Server port (default: `8000`)
- `REQUIRE_AUTH`: Enable Entra auth + RBAC checks (`false` by default locally)
- `ENTRA_TENANT_ID`: Entra tenant ID (required when auth enabled)
- `ENTRA_API_APP_ID`: API app registration ID (audience owner)
- `ENTRA_CLIENT_APP_ID`: Client app registration ID (token caller)
- `ENTRA_CLIENT_ID`: Client app registration ID used for token acquisition (required when auth enabled)
- `ENTRA_API_AUDIENCE`: API audience (recommended)
- `ENTRA_AUDIENCE`: Effective token audience used by validator (set to API audience)
- `ENTRA_AUTHORITY`: Authority URL (defaults from tenant when omitted)
- `ENTRA_ISSUER`: Expected token issuer (defaults from authority when omitted)
- `ENTRA_JWKS_URL`: JWKS endpoint (defaults from authority when omitted)
- `ENTRA_JWKS_CACHE_TTL_SECONDS`: JWKS cache TTL seconds (default: `300`)
- `SMOKE_BASE_URL`: Base URL for live smoke tests
- `MAF_PROVIDER`: Provider (default: `foundry`)
- `MAF_MODEL`: Model ID for provider (default: `gpt-4o-mini`)
- `OPENAI_API_KEY`: Required when `MAF_PROVIDER=openai`
- `FOUNDRY_PROJECTS_ENDPOINT`: Azure AI Foundry project endpoint
- `FOUNDRY_MODEL_DEPLOYMENT_NAME`: Foundry deployment name
- `APPLICATIONINSIGHTS_CONNECTION_STRING`: Azure Monitor connection string
- `OTEL_SERVICE_NAME`: OpenTelemetry service name
- `ENABLE_INSTRUMENTATION`: Enable Agent Framework instrumentation (default: `true`)
- `ENABLE_MANUAL_HTTP_INSTRUMENTATION`: Optional fallback to manually instrument FastAPI/requests (default: `false`; keep disabled to avoid duplicate/detached spans when using Azure Monitor distro)

See `.env.example` for a complete template.

## Local Commands

From `agents/01-researcher-agent`:

- `make install-dev` – install package with dev + test extras
- `make run` – run uvicorn locally with `REQUIRE_AUTH=false` and `ENABLE_TELEMETRY=false`
- `make up` – start local Docker container with `REQUIRE_AUTH=false` and `ENABLE_TELEMETRY=false`
- `make up-build` – rebuild and start local Docker container with `REQUIRE_AUTH=false` and `ENABLE_TELEMETRY=false`
- `make format` – format code (`black`)
- `make lint` – lint code (`ruff`)
- `make test` – run unit tests (`pytest`, auth disabled by default)
- `make verify` – run lint + format-check + tests
- `make smoke` – run live smoke tests (`tests/test_smoke_live.py`)
- `make test-smoke` – start local server and run smoke tests with auth disabled
- `make verify-deployment` – verify health/research/stream endpoints

From repo root:

- `make format`, `make lint`, `make test`, `make verify`, `make smoke`
- `make compose-up`, `make compose-down`, `make compose-logs`

## Observability & KQL

- Telemetry is configured in `app/core/observability/telemetry.py`.
- If `APPLICATIONINSIGHTS_CONNECTION_STRING` is not set, telemetry export is skipped.
- In this dev profile, MAF observability records full prompt/response content and node-level events (`node.researcher`, `node.reviewer`, `node.writer`) to align with LangGraph-style trace detail.
- Query pack: `scripts/kusto/kql/*.kql`
- Execute one query:
  - `scripts/kusto/run_kql.sh scripts/kusto/kql/05_auth_outcomes.kql 24h table`
- Execute full suite:
  - `scripts/kusto/run_suite.sh 24h`
  - `scripts/kusto/run-observability-suite.sh`

## Tests

Coverage includes:

- Health and research routes
- Research service behavior
- Entra auth, token validation, and RBAC dependencies
- Live smoke tests

## Script Entry Points

Agent-level scripts:

- `scripts/format.sh`
- `scripts/lint.sh`
- `scripts/test.sh`
- `scripts/test_smoke.sh`
- `scripts/verify_deployment.sh`

Repo-level wrappers:

- `scripts/format.sh`
- `scripts/lint.sh`
- `scripts/test.sh`
- `scripts/verify_deployment.sh`

Examples:

- Local no-auth verification: `bash scripts/verify_deployment.sh --env local`
- Azure verification: `bash scripts/verify_deployment.sh --env azure --base-url https://<container-app-fqdn>`
- Azure verification with explicit auth: `bash scripts/verify_deployment.sh --env azure --base-url https://<container-app-fqdn> --tenant-id <tenant> --client-id <client-app-id> --client-secret <secret> --scope <api://<api-app-id>/.default>`
