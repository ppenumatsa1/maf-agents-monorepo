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
    """MAF-backed workflow (researcher → reviewer → writer).

    Uses WorkflowBuilder to orchestrate researcher -> reviewer -> writer.
    """

    def __init__(self) -> None:
        self._config = MAFConfig.from_env()
        self._workflow = None

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
                run_result = await workflow.run(prompt)

        outputs = run_result.get_outputs() if hasattr(run_result, "get_outputs") else []
        return self._format_outputs(cast(list[object], outputs))

    async def stream(self, request: ResearchRequest) -> AsyncGenerator[StreamChunk, None]:
        with start_span("app.workflow.stream", {"topic": request.topic}):
            async with get_agents_provider(self._config) as provider:
                workflow = await self._build_workflow(provider)
                prompt = build_task_prompt(request)
                stream = workflow.run(prompt, stream=True)
                by_executor: dict[str, list[str]] = {}

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
                    yield {
                        "event": "output",
                        "executor": executor_id,
                        "text": text,
                    }

                final_result = await stream.get_final_response()
                final_outputs = (
                    final_result.get_outputs() if hasattr(final_result, "get_outputs") else []
                )
                formatted = self._format_outputs(
                    cast(list[object], final_outputs),
                    by_executor=by_executor,
                )
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
    ) -> dict[str, str]:
        researcher_text = self._joined_executor_output(by_executor, "ResearcherAgent")
        reviewer_text = self._joined_executor_output(by_executor, "ReviewerAgent")
        writer_text = self._joined_executor_output(by_executor, "WriterAgent")

        ordered: list[tuple[str, str]] = []
        for output in outputs:
            text = self._coerce_text(output).strip()
            if not text:
                continue
            ordered.append((self._coerce_author(output), text))
            if not researcher_text and self._looks_like_agent(output, "ResearcherAgent"):
                researcher_text = text
            if not reviewer_text and self._looks_like_agent(output, "ReviewerAgent"):
                reviewer_text = text
            if not writer_text and self._looks_like_agent(output, "WriterAgent"):
                writer_text = text

        ordered_texts = [text for _, text in ordered]
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

        summary = (writer_text or reviewer_text or researcher_text)[:500]
        return {
            "summary": summary,
            "draft": writer_text,
            "review": reviewer_text,
        }

    def _summarize(self, outputs: list[object]) -> str:
        for item in reversed(outputs):
            text = self._coerce_text(item)
            if text:
                return text[:500]
        return ""

    def _joined_executor_output(
        self,
        by_executor: dict[str, list[str]] | None,
        executor_name: str,
    ) -> str:
        if not by_executor:
            return ""
        return "".join(by_executor.get(executor_name, [])).strip()

    def _coerce_author(self, value: object) -> str:
        if isinstance(value, AgentResponse):
            if value.messages:
                return value.messages[0].author_name or ""
            return ""
        if isinstance(value, AgentResponseUpdate):
            author_name = getattr(value, "author_name", "")
            return author_name if isinstance(author_name, str) else ""
        return ""

    def _looks_like_agent(self, value: object, agent_name: str) -> bool:
        return self._coerce_author(value).lower() == agent_name.lower()

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
