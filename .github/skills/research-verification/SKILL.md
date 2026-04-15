---
name: research-verification
description: Validate researcher-agent quality gates and deployment endpoints.
argument-hint: Run format/lint/test/smoke/deployment verification for 01-researcher-agent.
---

# Research Verification Skill

Use this skill when asked to run or troubleshoot formatting, linting, tests, smoke checks, or deployment endpoint verification for the researcher agent.

## Commands

From repo root:

- bash scripts/format.sh
- bash scripts/lint.sh
- bash scripts/test.sh
- bash scripts/verify_deployment.sh --env local
- bash scripts/verify_deployment.sh --env azure

From agent root (agents/01-researcher-agent):

- bash scripts/format.sh
- bash scripts/lint.sh
- bash scripts/test.sh
- bash scripts/test_smoke.sh
- bash scripts/verify_deployment.sh --env local
- bash scripts/verify_deployment.sh --env azure

## Verification Expectations

- Local mode defaults to no auth.
- Azure mode defaults to auth and resolves base URL from CONTAINER_APP_FQDN when available.
- Health endpoint must return HTTP 200 with {"status":"ok"}.
- Research endpoint should return topic, draft, review_notes, and summary.
- Stream endpoint should return text/event-stream and emit data frames.

## Troubleshooting Notes

- If local research endpoints return 5xx, verify FOUNDRY_PROJECTS_ENDPOINT and model deployment environment settings.
- If Azure auth token acquisition fails, verify ENTRA_TENANT_ID, ENTRA_CLIENT_ID, ENTRA_CLIENT_SECRET, and ENTRA_SCOPE.
