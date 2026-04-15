from typing import AsyncGenerator, cast

from agent_framework import AgentResponse, AgentResponseUpdate, WorkflowBuilder, WorkflowEvent

from app.api.v1.schemas.research import ResearchRequest
from app.core.config import MAFConfig
from app.core.observability.telemetry import emit_business_event, start_span
from app.maf.agents import create_researcher, create_reviewer, create_writer
from app.maf.clients import get_agents_provider
from app.maf.prompts import build_task_prompt

StreamChunk = dict[str, str]


class ResearchWorkflow:
    """MAF-backed workflow (researcher → reviewer → writer).

    Uses WorkflowBuilder to orchestrate researcher -> reviewer -> writer.
    """

    def __init__(self) -> None:
        self._config = MAFConfig.from_env()

    async def _build_workflow(self, provider):
        model = self._config.foundry_model_deployment_name or self._config.model
        with start_span("app.workflow.build", {"model": model}):
            researcher = await create_researcher(provider, model)
            reviewer = await create_reviewer(provider, model)
            writer = await create_writer(provider, model)
            return (
                WorkflowBuilder(start_executor=researcher)
                .add_edge(researcher, reviewer)
                .add_edge(reviewer, writer)
                .build()
            )

    async def run(self, request: ResearchRequest) -> dict:
        with start_span("app.workflow.run", {"topic": request.topic}):
            async with get_agents_provider(self._config) as provider:
                workflow = await self._build_workflow(provider)
                prompt = build_task_prompt(request)
                emit_business_event(
                    "research.workflow.prompt",
                    {
                        "topic": request.topic or "",
                        "prompt": prompt,
                        "stream": False,
                    },
                )
                run_result = await workflow.run(prompt)

        outputs = run_result.get_outputs() if hasattr(run_result, "get_outputs") else []
        formatted, metadata = self._format_outputs(cast(list[object], outputs))
        emit_business_event("research.workflow.outputs", metadata)
        return formatted

    async def stream(self, request: ResearchRequest) -> AsyncGenerator[StreamChunk, None]:
        with start_span("app.workflow.stream", {"topic": request.topic}):
            async with get_agents_provider(self._config) as provider:
                workflow = await self._build_workflow(provider)
                prompt = build_task_prompt(request)
                emit_business_event(
                    "research.workflow.prompt",
                    {
                        "topic": request.topic or "",
                        "prompt": prompt,
                        "stream": True,
                    },
                )
                stream = workflow.run(prompt, stream=True)
                by_executor: dict[str, list[str]] = {}
                output_chunks_by_executor: dict[str, int] = {}
                output_chars_by_executor: dict[str, int] = {}

                async for event in stream:
                    if not isinstance(event, WorkflowEvent):
                        continue
                    executor_id = getattr(event, "executor_id", None) or "agent"
                    node_span = self._node_span_name(executor_id)

                    if event.type == "executor_invoked":
                        emit_business_event(
                            "research.workflow.node.invoked",
                            {
                                "executor": executor_id,
                                "node": node_span,
                            },
                        )
                        yield {
                            "event": "executor_invoked",
                            "executor": executor_id,
                        }
                        continue

                    if event.type == "executor_completed":
                        emit_business_event(
                            "research.workflow.node.completed",
                            {
                                "executor": executor_id,
                                "node": node_span,
                            },
                        )
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

                    by_executor.setdefault(executor_id, []).append(text)
                    output_chunks = output_chunks_by_executor.get(executor_id, 0) + 1
                    output_chunks_by_executor[executor_id] = output_chunks
                    output_chars = output_chars_by_executor.get(executor_id, 0) + len(text)
                    output_chars_by_executor[executor_id] = output_chars

                    if output_chunks == 1:
                        emit_business_event(
                            "research.workflow.node.first_output",
                            {
                                "executor": executor_id,
                                "node": node_span,
                                "text.length": len(text),
                                "output_chunks": output_chunks,
                                "output_chars": output_chars,
                            },
                        )
                    elif output_chunks % 20 == 0:
                        emit_business_event(
                            "research.workflow.node.progress",
                            {
                                "executor": executor_id,
                                "node": node_span,
                                "output_chunks": output_chunks,
                                "output_chars": output_chars,
                            },
                        )
                    yield {
                        "event": "output",
                        "executor": executor_id,
                        "text": text,
                    }

                final_result = await stream.get_final_response()
                final_outputs = (
                    final_result.get_outputs() if hasattr(final_result, "get_outputs") else []
                )
                formatted, metadata = self._format_outputs(
                    cast(list[object], final_outputs),
                    by_executor=by_executor,
                )
                for executor_id, chunks in output_chunks_by_executor.items():
                    emit_business_event(
                        "research.workflow.node.summary",
                        {
                            "executor": executor_id,
                            "node": self._node_span_name(executor_id),
                            "output_chunks": chunks,
                            "output_chars": output_chars_by_executor.get(executor_id, 0),
                        },
                    )
                emit_business_event("research.workflow.outputs", {**metadata, "stream": True})
                summary = formatted.get("summary", "")
                if summary:
                    yield {
                        "event": "summary",
                        "executor": "workflow",
                        "text": summary,
                    }

    def _format_outputs(
        self,
        outputs: list[object],
        *,
        by_executor: dict[str, list[str]] | None = None,
    ) -> tuple[dict[str, str], dict[str, str | bool | int | float]]:
        researcher_text = self._joined_executor_output(by_executor, "ResearcherAgent")
        reviewer_text = self._joined_executor_output(by_executor, "ReviewerAgent")
        writer_text = self._joined_executor_output(by_executor, "WriterAgent")

        ordered_texts: list[str] = []
        for output in outputs:
            text = self._coerce_text(output).strip()
            if not text:
                continue
            ordered_texts.append(text)

        if not researcher_text and ordered_texts:
            researcher_text = ordered_texts[0]
        if not reviewer_text and len(ordered_texts) >= 2:
            reviewer_text = ordered_texts[1]
        elif not reviewer_text and ordered_texts:
            reviewer_text = ordered_texts[-1]
        if not writer_text and len(ordered_texts) >= 3:
            writer_text = ordered_texts[2]
        elif not writer_text and ordered_texts:
            writer_text = ordered_texts[-1]

        summary_source = "writer"
        if not writer_text and reviewer_text:
            summary_source = "reviewer"
        elif not writer_text and not reviewer_text and researcher_text:
            summary_source = "researcher"
        elif not writer_text and not reviewer_text and not researcher_text and ordered_texts:
            summary_source = "ordered_fallback"

        summary_candidate = writer_text or reviewer_text or researcher_text
        summary_truncated = len(summary_candidate) > 500
        summary = summary_candidate[:500]

        formatted = {
            "summary": summary,
            "draft": writer_text,
            "review": reviewer_text,
        }
        metadata: dict[str, str | bool | int | float] = {
            "summary.length": len(summary),
            "draft.length": len(writer_text),
            "review.length": len(reviewer_text),
            "summary.truncated": summary_truncated,
            "summary.source": summary_source,
            "fallback.used": summary_source != "writer",
        }
        return formatted, metadata

    def _joined_executor_output(
        self,
        by_executor: dict[str, list[str]] | None,
        executor_name: str,
    ) -> str:
        if not by_executor:
            return ""
        return "".join(by_executor.get(executor_name, [])).strip()

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

    def _node_span_name(self, executor_id: str) -> str:
        normalized = (executor_id or "agent").lower()
        if "researcher" in normalized:
            return "node.researcher"
        if "reviewer" in normalized:
            return "node.reviewer"
        if "writer" in normalized:
            return "node.writer"
        return "node.agent"
