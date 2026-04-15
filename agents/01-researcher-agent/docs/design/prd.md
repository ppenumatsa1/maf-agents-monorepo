# Product Requirements Document (PRD)

## Goal

Deliver a researcher agent that performs research, drafts a response, reviews it, and returns a summary via FastAPI.

## Users

- Developers integrating the agent into applications
- API consumers calling `/v1/research` and `/v1/research/stream`

## Key Requirements

- FastAPI-only API surface with versioned routes under `/v1`
- `/health` endpoint
- Researcher → writer → reviewer workflow via MAF
- SSE streaming endpoint for research output
- Entra JWT auth with route-level RBAC when enabled
- Local-first default with auth disabled (`REQUIRE_AUTH=false`)
- OpenTelemetry + Azure Monitor/App Insights telemetry for API/auth/workflow signals
- Operational KQL suite for observability triage and dashboards

## Non-Goals

- Cross-agent shared runtime code
- Non-FastAPI API surfaces
- Built-in external web search toolchain in this baseline agent

## Current API/Behavior Notes

- `POST /v1/research` requires role `Research.Read` when auth is enabled.
- `POST /v1/research/stream` requires role `Research.Write` when auth is enabled.
- With auth disabled locally, role checks are bypassed and requests execute as anonymous principal.
