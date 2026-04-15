from typing import AsyncGenerator, cast

from agent_framework import AgentResponse, AgentResponseUpdate, WorkflowBuilder, WorkflowEvent

from app.api.v1.schemas.research import ResearchRequest
from app.core.config import MAFConfig
from app.core.observability.telemetry import start_span
from app.maf.agents import create_researcher, create_reviewer, create_writer
from app.maf.clients import get_agents_provider
from app.maf.prompts import build_task_prompt

StreamChunk = dict[str, str]


class ResearchWorkflow:
    """MAF-backed workflow (researcher → writer → reviewer).

    Uses WorkflowBuilder to orchestrate researcher -> writer -> reviewer.
    """

    def __init__(self) -> None:
        self._config = MAFConfig.from_env()
        self._workflow = None

    async def _build_workflow(self, provider):
        model = self._config.foundry_model_deployment_name or self._config.model
        with start_span("app.workflow.build", {"model": model}):
            researcher = await create_researcher(provider, model)
            writer = await create_writer(provider, model)
            reviewer = await create_reviewer(provider, model)
            return (
                WorkflowBuilder(start_executor=researcher)
                .add_edge(researcher, writer)
                .add_edge(writer, reviewer)
                .build()
            )

    async def run(self, request: ResearchRequest) -> dict:
        with start_span("app.workflow.run", {"topic": request.topic}):
            async with get_agents_provider(self._config) as provider:
                workflow = await self._build_workflow(provider)
                prompt = build_task_prompt(request)
                stream = workflow.run(prompt, stream=True)
                by_executor: dict[str, list[str]] = {}
                executor_order: list[str] = []
                async for event in stream:
                    if not isinstance(event, WorkflowEvent):
                        continue
                    if event.type != "output" or not isinstance(event.data, AgentResponseUpdate):
                        continue
                    if not event.data.text:
                        continue
                    executor_id = getattr(event, "executor_id", None) or "agent"
                    if executor_id not in by_executor:
                        executor_order.append(executor_id)
                    by_executor.setdefault(executor_id, []).append(event.data.text)
                run_result = await stream.get_final_response()

        # Prefer streamed text chunks for deterministic extraction of draft/review.
        collected = [
            (executor_id, "".join(chunks).strip())
            for executor_id, chunks in by_executor.items()
            if "".join(chunks).strip()
        ]
        ordered_texts = [
            text for executor_id in executor_order for eid, text in collected if eid == executor_id
        ]

        researcher_text = "".join(by_executor.get("ResearcherAgent", [])).strip()
        writer_text = "".join(by_executor.get("WriterAgent", [])).strip()
        reviewer_text = "".join(by_executor.get("ReviewerAgent", [])).strip()

        if not researcher_text and ordered_texts:
            researcher_text = ordered_texts[0]
        if not writer_text and len(ordered_texts) >= 2:
            writer_text = ordered_texts[1]
        elif not writer_text and ordered_texts:
            writer_text = ordered_texts[0]
        if not reviewer_text and len(ordered_texts) >= 3:
            reviewer_text = ordered_texts[2]
        elif not reviewer_text and ordered_texts:
            reviewer_text = ordered_texts[-1]

        summary = reviewer_text or writer_text or researcher_text
        if not summary:
            outputs = run_result.get_outputs() if hasattr(run_result, "get_outputs") else []
            summary = self._summarize(cast(list[object], outputs))

        return {
            "summary": summary[:500] if summary else "",
            "draft": writer_text,
            "review": reviewer_text,
        }

    async def stream(self, request: ResearchRequest) -> AsyncGenerator[StreamChunk, None]:
        with start_span("app.workflow.stream", {"topic": request.topic}):
            async with get_agents_provider(self._config) as provider:
                workflow = await self._build_workflow(provider)
                prompt = build_task_prompt(request)
                stream = workflow.run(prompt, stream=True)
                buffers: dict[str, str] = {}

                async def flush_executor(executor_id: str) -> AsyncGenerator[StreamChunk, None]:
                    pending = buffers.get(executor_id, "")
                    if pending:
                        yield {
                            "event": "output",
                            "executor": executor_id,
                            "text": pending,
                        }
                        buffers[executor_id] = ""

                async for event in stream:
                    if not isinstance(event, WorkflowEvent):
                        continue
                    executor_id = getattr(event, "executor_id", None) or "agent"

                    if event.type == "executor_invoked":
                        yield {
                            "event": "executor_invoked",
                            "executor": executor_id,
                        }
                        continue

                    if event.type == "executor_completed":
                        async for chunk in flush_executor(executor_id):
                            yield chunk
                        yield {
                            "event": "executor_completed",
                            "executor": executor_id,
                        }
                        continue

                    if event.type != "output":
                        continue

                    text = self._coerce_text(event.data)
                    if not text:
                        continue

                    buffers[executor_id] = f"{buffers.get(executor_id, '')}{text}"
                    if self._should_flush_buffer(buffers[executor_id]):
                        async for chunk in flush_executor(executor_id):
                            yield chunk

                for executor_id in list(buffers.keys()):
                    async for chunk in flush_executor(executor_id):
                        yield chunk

                final_result = await stream.get_final_response()
                final_outputs = (
                    final_result.get_outputs() if hasattr(final_result, "get_outputs") else []
                )
                summary = self._summarize(cast(list[object], final_outputs))
                if summary:
                    yield {
                        "event": "summary",
                        "executor": "workflow",
                        "text": summary,
                    }

    def _format_response(self, outputs: list[object]) -> dict:
        texts = [self._coerce_text(output) for output in outputs]
        texts = [text for text in texts if text]

        draft = texts[-2] if len(texts) >= 2 else ""
        review = texts[-1] if texts else ""

        return {
            "summary": self._summarize(outputs),
            "draft": draft,
            "review": review,
        }

    def _summarize(self, outputs: list[object]) -> str:
        for item in reversed(outputs):
            text = self._coerce_text(item)
            if text:
                return text[:500]
        return ""

    def _coerce_text(self, value: object) -> str:
        if isinstance(value, AgentResponse):
            return value.text or ""
        if isinstance(value, AgentResponseUpdate):
            return value.text or ""
        if isinstance(value, str):
            return value

        text_value = getattr(value, "text", None)
        if isinstance(text_value, str):
            return text_value

        return ""

    def _should_flush_buffer(self, value: str) -> bool:
        if not value:
            return False
        if "\n" in value:
            return True
        if len(value) >= 120:
            return True
        if len(value) >= 30 and value.rstrip().endswith((".", "!", "?", ":", ";")):
            return True
        return False
