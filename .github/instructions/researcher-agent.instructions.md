---
applyTo: "agents/01-researcher-agent/**"
---

## Researcher Agent Coding Rules

- Keep API contracts in app/api/v1/schemas and route handlers in app/api/v1/routers.
- Put feature logic under app/modules and keep router files thin.
- Use app/maf/workflows/research_workflow.py as the primary orchestration entrypoint.
- Avoid introducing app/domain package; modules is the canonical feature layer.
- Preserve role checks:
  - /v1/research requires Research.Read
  - /v1/research/stream requires Research.Write

## Local-First Validation

- For local tests and smoke checks, default to REQUIRE_AUTH=false.
- Keep smoke coverage for:
  - GET /health
  - POST /v1/research
  - POST /v1/research/stream
- If changing response shapes, update tests and verify_deployment.sh checks in the same change.

## Script Conventions

- Format: agents/01-researcher-agent/scripts/format.sh
- Lint: agents/01-researcher-agent/scripts/lint.sh
- Tests: agents/01-researcher-agent/scripts/test.sh
- Smoke: agents/01-researcher-agent/scripts/test_smoke.sh
- Deployment checks: agents/01-researcher-agent/scripts/verify_deployment.sh

Keep scripts idempotent and runnable both in local shells and CI jobs.
