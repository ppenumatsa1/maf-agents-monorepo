from typing import AsyncGenerator

from app.api.v1.schemas.research import ResearchRequest, ResearchResponse
from app.core.observability.telemetry import emit_business_event, record_stream_chunk, start_span


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
            response = ResearchResponse(**result)
            emit_business_event(
                "research.service.output",
                {
                    "summary.length": len(response.summary or ""),
                    "summary": response.summary or "",
                    "draft.length": len(response.draft or ""),
                    "draft": response.draft or "",
                    "review.length": len(response.review or ""),
                    "review": response.review or "",
                    "stream": False,
                },
            )
            return response

    async def stream(self, request: ResearchRequest) -> AsyncGenerator[str | dict[str, str], None]:
        with start_span(
            "app.service.research_stream",
            {"topic": request.topic, "has_constraints": bool(request.constraints)},
        ):
            chunk_index = 0
            dict_chunks = 0
            output_chunks = 0
            completed = False
            try:
                async for chunk in self._workflow.stream(request):
                    chunk_index += 1
                    record_stream_chunk(
                        chunk_index=chunk_index,
                        attributes={
                            "topic.length": len(request.topic or ""),
                            "has_constraints": bool(request.constraints),
                        },
                    )
                    if isinstance(chunk, dict):
                        dict_chunks += 1
                        if str(chunk.get("event", "update")) == "output":
                            output_chunks += 1

                    if chunk_index == 1 or chunk_index % 25 == 0:
                        emit_business_event(
                            "research.service.stream.progress",
                            {
                                "chunk_index": chunk_index,
                                "dict_chunks": dict_chunks,
                                "output_chunks": output_chunks,
                            },
                        )
                    yield chunk
                completed = True
            except Exception as exc:
                emit_business_event(
                    "research.service.stream.failed",
                    {
                        "chunk_index": chunk_index,
                        "dict_chunks": dict_chunks,
                        "output_chunks": output_chunks,
                        "reason": type(exc).__name__,
                    },
                )
                raise
            finally:
                emit_business_event(
                    "research.service.stream.completed",
                    {
                        "completed": completed,
                        "total_chunks": chunk_index,
                        "dict_chunks": dict_chunks,
                        "output_chunks": output_chunks,
                    },
                )
