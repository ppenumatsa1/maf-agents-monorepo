# MAF Agents Monorepo

## Summary

Monorepo for Microsoft Agent Framework (MAF) agents deployed to Azure Container Apps with azd.
Each agent is an independently deployable FastAPI service with consistent API structure, auth toggles, and observability patterns.

## Goals

- One deployable service per agent
- MAF-first workflow modeling
- No shared runtime Python code across agents
- Azure-ready from day one (ACA + ACR + App Insights)
- Environment-driven configuration (12-factor)

## What’s Included

- Agent-local FastAPI app (`app/main.py`)
- Versioned API routes under `app/api/v1/routers`
- Domain modules under `app/modules/*` (for example `app/modules/research`)
- Security/auth helpers under `app/core/security`
- MAF workflows, prompts, and tools under `app/maf`
- Structured logging + OpenTelemetry + Azure Monitor wiring
- Dockerfile per agent for containerized runs
- Root Makefile to orchestrate agent tasks
- Infra-as-code with Bicep modules
- Shared KQL query suite and runner scripts in `scripts/kusto/`

## Structure

- `agents/`: Self-contained agents
- `infra/`: Infrastructure-as-code (Bicep) scaffolding
- `scripts/kusto/`: Shared KQL queries, run scripts, and results

## Prerequisites (Ubuntu/Debian)

1. Update packages  
   `sudo apt-get update`
2. Install Python 3.11 and venv  
   `sudo apt-get install -y python3.11 python3.11-venv python3-pip`
3. Install Docker (for container builds)  
   `sudo apt-get install -y docker.io`
4. Install Azure CLI  
   `curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash`
5. Install Azure Developer CLI (azd)  
   `curl -fsSL https://aka.ms/install-azd.sh | sudo bash`
6. Install Make (optional)  
   `sudo apt-get install -y make`

## Quickstart (azd)

1. Clone the repo and enter it
   - `git clone https://github.com/ppenumatsa1/maf-agents-monorepo.git`
   - `cd maf-agents-monorepo`
2. Verify Docker is running
   - `docker version`
3. Authenticate and run azd
   - `azd auth login`
   - `azd env new`
   - `azd up`

## Local Development

Agent setup and API usage are documented in `agents/01-researcher-agent/README.md`.

Common local workflow targets from repo root:

- `make install-dev` – install agent dev/test dependencies
- `make run` – run the default agent locally
- `make format` – format code
- `make lint` – run lint checks
- `make test` – run unit tests (`REQUIRE_AUTH=false` by default)
- `make verify` – run lint + formatting checks + tests
- `make verify-deployment` – run endpoint verification checks
- `make smoke` – run live smoke tests against local service
- `make compose-up` / `make compose-down` / `make compose-logs` – manage local Docker Compose stack

Root script wrappers are also available:

- `bash scripts/format.sh`
- `bash scripts/lint.sh`
- `bash scripts/test.sh`
- `bash scripts/verify_deployment.sh --env local`
- `bash scripts/verify_deployment.sh --env azure`

Auth is disabled by default for local workflows (`REQUIRE_AUTH=false`).
Enable Entra auth locally by setting `REQUIRE_AUTH=true` and supplying required `ENTRA_*` values.

## Observability & KQL Workflow

- App emits OpenTelemetry spans/metrics and Azure Monitor telemetry when `APPLICATIONINSIGHTS_CONNECTION_STRING` is set.
- KQL query pack is under `scripts/kusto/kql/`.
- Run one query:
  - `scripts/kusto/run_kql.sh scripts/kusto/kql/01_research_requests_overview.kql 24h table`
- Run full suite and store JSON results under `scripts/kusto/results/<timestamp>/`:
  - `scripts/kusto/run_suite.sh 24h`
  - `scripts/kusto/run-observability-suite.sh --timespan 24h`

## Verify Azure Deployment

Run smoke tests against a deployed endpoint:

- `SMOKE_BASE_URL=https://<your-app>.azurecontainerapps.io python -m pytest agents/01-researcher-agent/tests/test_smoke_live.py`

## Agent Design Docs

Each agent owns design artifacts under `docs/design` (PRD, tech stack, project structure, user flow).

| Agent               | Workflow                           | Docs                            |
| ------------------- | ---------------------------------- | ------------------------------- |
| 01-researcher-agent | Research → write → review workflow | agents/01-researcher-agent/docs |

## License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.

## Disclaimer

This repository is provided for educational and demonstration purposes only. It is not intended for production use as-is.
You are responsible for reviewing, testing, and securing any code, configurations, credentials, or deployment artifacts before using them in real systems.
Do not deploy this repository without your own security review, compliance checks, and operational hardening (logging, alerting, backups, access controls, and cost safeguards).
By using this repository, you acknowledge that you assume all risks associated with its use.
