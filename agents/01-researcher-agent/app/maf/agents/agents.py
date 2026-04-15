from typing import Any, Protocol

from app.core.observability.telemetry import start_span
from app.maf.prompts import (
    RESEARCHER_INSTRUCTIONS,
    REVIEWER_INSTRUCTIONS,
    WRITER_INSTRUCTIONS,
)
from app.maf.tools import web_search


class AgentsProvider(Protocol):
    async def create_agent(
        self,
        *,
        name: str,
        instructions: str,
        model: str,
        tools: list[Any],
    ) -> Any: ...


async def create_researcher(provider: AgentsProvider, model: str):
    with start_span("app.agent.create", {"agent.name": "ResearcherAgent", "model": model}):
        return await provider.create_agent(
            name="ResearcherAgent",
            instructions=RESEARCHER_INSTRUCTIONS,
            model=model,
            tools=[web_search],
        )


async def create_writer(provider: AgentsProvider, model: str):
    with start_span("app.agent.create", {"agent.name": "WriterAgent", "model": model}):
        return await provider.create_agent(
            name="WriterAgent",
            instructions=WRITER_INSTRUCTIONS,
            model=model,
            tools=[],
        )


async def create_reviewer(provider: AgentsProvider, model: str):
    with start_span("app.agent.create", {"agent.name": "ReviewerAgent", "model": model}):
        return await provider.create_agent(
            name="ReviewerAgent",
            instructions=REVIEWER_INSTRUCTIONS,
            model=model,
            tools=[],
        )


__all__ = ["create_researcher", "create_reviewer", "create_writer"]
