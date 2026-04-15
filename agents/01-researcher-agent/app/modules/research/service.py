from typing import AsyncGenerator

from app.api.v1.schemas.research import ResearchRequest, ResearchResponse
from app.core.observability.telemetry import record_stream_chunk, start_span


class ResearchService:
    def __init__(self) -> None:
        from app.maf import ResearchWorkflow

        self._workflow = ResearchWorkflow()

    async def run(self, request: ResearchRequest) -> ResearchResponse:
        with start_span(
            "app.service.research",
            {"topic": request.topic, "has_constraints": bool(request.constraints)},
        ):
            result = await self._workflow.run(request)
            return ResearchResponse(**result)

    async def stream(self, request: ResearchRequest) -> AsyncGenerator[str | dict[str, str], None]:
        with start_span(
            "app.service.research_stream",
            {"topic": request.topic, "has_constraints": bool(request.constraints)},
        ):
            chunk_index = 0
            async for chunk in self._workflow.stream(request):
                chunk_index += 1
                record_stream_chunk(
                    chunk_index=chunk_index,
                    attributes={
                        "topic.length": len(request.topic or ""),
                        "has_constraints": bool(request.constraints),
                    },
                )
                yield chunk
