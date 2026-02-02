# 01-researcher-agent

Researcher agent built with FastAPI and MS Agent Framework (MAF).

## Environment Variables

- PORT: Server port (default: 8000)
- SMOKE_BASE_URL: Base URL for live smoke tests
- MAF_PROVIDER: MAF provider (default: foundry)
- MAF_MODEL: Model ID for the provider (default: gpt-4o-mini)
- OPENAI_API_KEY: Required when MAF_PROVIDER=openai
- FOUNDRY_PROJECTS_ENDPOINT: Azure AI Foundry project endpoint
- FOUNDRY_MODEL_DEPLOYMENT_NAME: Foundry model deployment name
- APPLICATIONINSIGHTS_CONNECTION_STRING: Azure Monitor connection string
- OTEL_SERVICE_NAME: OpenTelemetry service name
- ENABLE_INSTRUMENTATION: Enable Agent Framework instrumentation (default: true)
- ENABLE_SENSITIVE_DATA: Allow sensitive telemetry (default: false)

See .env.example for a full template.

## Local Run

1. Install dependencies: `make install`
2. Run server: `make run`
3. Health check: GET /health

## Tests

- Unit tests: `make test`
- Live smoke tests: SMOKE_BASE_URL=http://localhost:8000 pytest tests/test_smoke_live.py -q

## Notes

MAF SequentialBuilder workflow lives in app/maf and is used for all requests.
