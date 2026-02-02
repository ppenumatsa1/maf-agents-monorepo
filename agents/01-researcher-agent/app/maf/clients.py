from contextlib import asynccontextmanager
from typing import AsyncIterator

from agent_framework.azure import AzureAIAgentsProvider
from azure.identity.aio import DefaultAzureCredential

from app.core.config import MAFConfig
from app.core.observability.telemetry import start_span


@asynccontextmanager
async def get_agents_provider(config: MAFConfig) -> AsyncIterator[AzureAIAgentsProvider]:
    with start_span("app.provider.azure_ai_agents"):
        async with DefaultAzureCredential() as credential:
            project_endpoint = config.foundry_projects_endpoint
            if not project_endpoint:
                raise ValueError("FOUNDRY_PROJECTS_ENDPOINT is required for Azure AI agents")
            async with AzureAIAgentsProvider(
                credential=credential,
                project_endpoint=project_endpoint,
            ) as provider:
                yield provider
