# Copilot Instructions - MAF Agents Monorepo

## Purpose

This repository is a production-ready monorepo for Microsoft Agent Framework (MAF) agents.
Copilot must follow these rules strictly to avoid architectural drift.

---

## Core Architecture Rules

- Each agent is fully self-contained and independently deployable.
- No shared runtime Python code across agents.
- Shared artifacts are allowed only at the repo root:
  - infra/
  - azure.yaml
  - root Makefile
  - root scripts/
- Agents must not import code from other agents.

---

## Tech Stack (Do Not Deviate)

- Language: Python
- API framework: FastAPI (only API surface)
- Agent runtime: MS Agent Framework https://github.com/microsoft/agent-framework
- Hosting: Azure Container Apps (ACA)
- Provisioning: azd
- Observability: OpenTelemetry → Application Insights / Azure Monitor

---

## Agent Layout

- Agents live under: agents/<nn>-<agent-name>/
- Each agent must include:
  - FastAPI entrypoint
  - MS Agent Framework workflow + agent loops
  - Clear separation of:
    - app/api (versioned HTTP routes + schemas)
    - app/modules (feature services and domain models)
    - app/core
    - app/maf
  - Per-agent scripts directory for quality and verification tasks
  - Per-agent Dockerfile and Makefile

---

## API Conventions

- APIs must be versioned under /v1
- Route modules must enforce the /v1 prefix (no unversioned routes)
- Health endpoint is mandatory:
  - /health

---

## Observability (Mandatory)

- OpenTelemetry traces, logs, and metrics are required.
- Export telemetry to Azure Application Insights.
- Standardize OTEL config via environment variables (service name, exporter endpoint, sampling).
- Correlation ID support is required:
  - Accept or generate x-correlation-id
  - Store in contextvars
  - Inject into all logs
  - Attach to OTEL spans (e.g., app.correlation_id)
  - Propagate to downstream HTTP calls

### Azure Monitor / App Insights KQL reuse

- Save reusable KQL queries in the repo under scripts/kusto/kql/ when team-shared.
- Prefer parameterized workbooks for repeatable analysis (correlation_id, operation_id, time range).
- Store workspace IDs in env vars (e.g., AZURE_LOG_ANALYTICS_WORKSPACE_ID).

### Verification workflow

- Keep deployment checks in agent-level scripts/verify_deployment.sh.
- Local verification defaults to no-auth checks.
- Azure verification should support Entra client credentials and auto-resolve CONTAINER_APP_FQDN from azd env.

---

## Configuration & Security

- 12-factor configuration (environment variables only)
- No secrets in code or config files
- Containers must run as non-root
- Production-safe defaults (timeouts, limits)

---

## Quality & Tooling

- Tests must be written with pytest and live under tests/
- Keep lint/format/sort configuration consistent across agents (ruff/black/isort)
- Prefer invoking quality checks via scripts (scripts/format.sh, scripts/lint.sh, scripts/test.sh).

---

## Documentation

- Each agent must include a README with:
  - Required environment variables
  - Local run instructions
  - Deployment notes

---

## Guidance for Copilot

- Prefer explicit, simple implementations over abstractions.
- Match the existing LangGraph monorepo structure exactly where applicable.
- When in doubt, mirror existing agent patterns instead of inventing new ones.
