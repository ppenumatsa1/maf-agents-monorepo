from typing import AsyncGenerator, cast

from agent_framework import AgentRunUpdateEvent, SequentialBuilder, WorkflowOutputEvent
from agent_framework import ChatMessage

from app.core.config import MAFConfig
from app.core.observability.telemetry import start_span
from app.domain.schemas.research import ResearchRequest
from app.maf.agents import create_researcher, create_reviewer, create_writer
from app.maf.clients import get_agents_provider
from app.maf.prompts import build_task_prompt


class ResearchWorkflow:
    """MAF-backed workflow (researcher → writer → reviewer).

    Uses SequentialBuilder when enabled; falls back to a local stub if disabled.
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
            return SequentialBuilder().participants([researcher, writer, reviewer]).build()

    async def run(self, request: ResearchRequest) -> dict:
        with start_span("app.workflow.run", {"topic": request.topic}):
            async with get_agents_provider(self._config) as provider:
                workflow = await self._build_workflow(provider)
                prompt = build_task_prompt(request)
                events = await workflow.run(prompt)

        outputs = []
        if hasattr(events, "get_outputs"):
            outputs = events.get_outputs()

        messages = outputs[-1] if outputs else []
        return self._format_response(cast(list[ChatMessage], messages))

    async def stream(self, request: ResearchRequest) -> AsyncGenerator[str, None]:
        with start_span("app.workflow.stream", {"topic": request.topic}):
            async with get_agents_provider(self._config) as provider:
                workflow = await self._build_workflow(provider)
                prompt = build_task_prompt(request)
                async for event in workflow.run_stream(prompt):
                    if isinstance(event, AgentRunUpdateEvent):
                        if event.data:
                            yield f"{event.executor_id}: {event.data}"
                    elif isinstance(event, WorkflowOutputEvent):
                        messages = cast(list[ChatMessage], event.data)
                        summary = self._summarize(messages)
                        yield f"Summary: {summary}"

    def _format_response(self, messages: list[ChatMessage]) -> dict:
        def last_text_by_name(name: str) -> str:
            for msg in reversed(messages):
                if msg.author_name and name in msg.author_name.lower() and msg.text:
                    return msg.text
            return ""

        assistant_texts = [
            msg.text for msg in messages if msg.role and msg.text and msg.role.value == "assistant"
        ]
        draft = last_text_by_name("writer")
        review = last_text_by_name("reviewer")

        if not draft and len(assistant_texts) >= 2:
            draft = assistant_texts[-2]
        if not review and assistant_texts:
            review = assistant_texts[-1]

        return {
            "summary": self._summarize(messages),
            "draft": draft,
            "review": review,
        }

    def _summarize(self, messages: list[ChatMessage]) -> str:
        for msg in reversed(messages):
            if msg.text:
                return msg.text[:500]
        return ""
