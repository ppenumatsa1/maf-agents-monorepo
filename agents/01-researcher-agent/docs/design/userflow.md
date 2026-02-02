# Researcher Agent User Flow

## Primary Flow

1. User submits a topic.
2. System runs researcher → writer → reviewer workflow.
3. System returns draft, review notes, and final summary.

## Inputs

- Topic (required)
- Constraints: audience, tone, length, time range (optional)

## Outputs

- Draft response
- Review notes
- Final summary

## Error Handling

- Missing topic → validation error
- Azure AI project not configured → request fails with configuration error

## Technical Flow (Request → Response)

1. HTTP request hits FastAPI route:
   [agents/01-researcher-agent/app/domain/routes/research.py](../../app/domain/routes/research.py)
2. Route calls service:
   [agents/01-researcher-agent/app/domain/services/research_service.py](../../app/domain/services/research_service.py)
3. Service runs MAF workflow:
   [agents/01-researcher-agent/app/maf/workflows/research_workflow.py](../../app/maf/workflows/research_workflow.py)
4. Workflow builds Azure AI agents via provider:
   [agents/01-researcher-agent/app/maf/clients.py](../../app/maf/clients.py)
5. Agents execute with prompts and tools:
   - Prompts: [agents/01-researcher-agent/app/maf/prompts/prompts.py](../../app/maf/prompts/prompts.py)
   - Tools: [agents/01-researcher-agent/app/maf/tools.py](../../app/maf/tools.py)
6. Workflow returns draft/review/summary to route and serializes:
   [agents/01-researcher-agent/app/domain/schemas/research.py](../../app/domain/schemas/research.py)

Note: Each request returns `X-Correlation-Id` and logs include `correlation_id`.
