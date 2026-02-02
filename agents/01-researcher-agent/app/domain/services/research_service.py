from typing import AsyncGenerator

from app.core.observability.telemetry import start_span
from app.domain.schemas.research import ResearchRequest, ResearchResponse
from app.maf import ResearchWorkflow


class ResearchService:
    def __init__(self) -> None:
        self._workflow = ResearchWorkflow()

    async def run(self, request: ResearchRequest) -> ResearchResponse:
        with start_span(
            "app.service.research",
            {"topic": request.topic, "has_constraints": bool(request.constraints)},
        ):
            result = await self._workflow.run(request)
            return ResearchResponse(**result)

    async def stream(self, request: ResearchRequest) -> AsyncGenerator[str, None]:
        with start_span(
            "app.service.research_stream",
            {"topic": request.topic, "has_constraints": bool(request.constraints)},
        ):
            async for chunk in self._workflow.stream(request):
                yield chunk
