from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from agent_framework.foundry import FoundryChatClient
from azure.identity.aio import DefaultAzureCredential

from app.core.config import MAFConfig
from app.core.observability.telemetry import record_auth_outcome, start_span


class FoundryAgentsProvider:
    def __init__(self, *, credential: DefaultAzureCredential, project_endpoint: str) -> None:
        self._credential = credential
        self._project_endpoint = project_endpoint

    async def create_agent(
        self,
        *,
        name: str,
        instructions: str,
        model: str,
        tools: list[Any],
    ) -> Any:
        client = FoundryChatClient(
            project_endpoint=self._project_endpoint,
            model=model,
            credential=self._credential,
        )
        # Keep each workflow invocation stateless so tool-call state does not leak
        # across sequential executors in a workflow run.
        return client.as_agent(
            name=name,
            instructions=instructions,
            tools=tools,
            default_options={"store": False},
        )


@asynccontextmanager
async def get_agents_provider(config: MAFConfig) -> AsyncIterator[FoundryAgentsProvider]:
    with start_span("app.provider.azure_ai_agents"):
        try:
            async with DefaultAzureCredential() as credential:
                project_endpoint = config.foundry_projects_endpoint
                if not project_endpoint:
                    raise ValueError("FOUNDRY_PROJECTS_ENDPOINT is required for Azure AI agents")
                provider = FoundryAgentsProvider(
                    credential=credential,
                    project_endpoint=project_endpoint,
                )
                record_auth_outcome(integration="azure_ai_agents", success=True)
                yield provider
        except Exception as exc:
            record_auth_outcome(
                integration="azure_ai_agents",
                success=False,
                reason=type(exc).__name__,
            )
            raise
