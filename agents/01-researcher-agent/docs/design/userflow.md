# Researcher Agent User Flow

## Primary Flow

1. User sends a request to `POST /v1/research` or `POST /v1/research/stream`.
2. Auth dependency resolves current principal:
   - Local default (`REQUIRE_AUTH=false`): anonymous principal allowed.
   - Auth enabled (`REQUIRE_AUTH=true`): Entra JWT validated and required route role enforced.
3. Route records request telemetry and calls the research service.
4. Service runs researcher → writer → reviewer workflow via MAF.
5. API returns summary payload (or stream chunks for SSE).

## Inputs

- Topic (required)
- Constraints: audience, tone, length, time range (optional)

## Outputs

- Draft response
- Review notes
- Final summary

## Error Handling

- Missing topic → validation error (422)
- Missing/invalid bearer token (when auth enabled) → 401
- Missing required role (when auth enabled) → 403
- Azure AI provider misconfiguration/runtime failure → request fails with error telemetry

## Technical Flow (Request → Response)

1. HTTP request hits FastAPI route:
   [agents/01-researcher-agent/app/api/v1/routers/research.py](../../app/api/v1/routers/research.py)
2. Route auth/RBAC dependencies execute:
   [agents/01-researcher-agent/app/core/security/dependencies.py](../../app/core/security/dependencies.py)
3. Route calls service:
   [agents/01-researcher-agent/app/modules/research/service.py](../../app/modules/research/service.py)
4. Service runs MAF workflow:
   [agents/01-researcher-agent/app/maf/workflows/research_workflow.py](../../app/maf/workflows/research_workflow.py)
5. Workflow builds Azure AI agents via provider:
   [agents/01-researcher-agent/app/maf/clients.py](../../app/maf/clients.py)
6. Agents execute prompts/tools and return data:
   - Prompts: [agents/01-researcher-agent/app/maf/prompts/prompts.py](../../app/maf/prompts/prompts.py)
   - Tools: [agents/01-researcher-agent/app/maf/tools.py](../../app/maf/tools.py)
7. Route serializes response schema:
   [agents/01-researcher-agent/app/api/v1/schemas/research.py](../../app/api/v1/schemas/research.py)

## Observability Flow

- Correlation ID middleware attaches `X-Correlation-Id` and `app.correlation_id` attributes.
- Route/service telemetry emits request start/completion/failure, stream chunk, and auth outcome signals.
- KQL suite in `scripts/kusto/kql` supports operational analysis (throughput, failures, latency, auth outcomes, dependencies).
