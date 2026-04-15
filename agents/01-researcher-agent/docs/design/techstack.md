# Tech Stack

- Language: Python
- API framework: FastAPI (`app/api/v1`)
- Agent runtime: Microsoft Agent Framework (MAF)
- Authentication/Authorization: Microsoft Entra JWT + route-level RBAC (`require_roles`)
- Hosting: Azure Container Apps
- Provisioning: azd + Bicep
- Observability: OpenTelemetry + Azure Monitor / Application Insights
- Local orchestration: Make + Docker Compose

Implementation notes:

- API and module layout uses `app/api/v1` + `app/modules/research`.
- Auth can be disabled locally with `REQUIRE_AUTH=false` for development/testing.
- KQL operational suite is maintained in `scripts/kusto/kql` with shell runners in `scripts/kusto`.
