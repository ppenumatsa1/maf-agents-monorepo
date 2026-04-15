# Copyright (c) Microsoft. All rights reserved.
# Simple single-file end-to-end workflow using Microsoft Agent Framework.
# Current focus: validate Researcher -> Reviewer -> Writer flow locally before modular refactors.
#
# Manual run examples from agents/01-researcher-agent:
#   python3 e2e_simple_workflow.py "AI safety"
#   python3 e2e_simple_workflow.py "AI safety" --stream
#   python3 e2e_simple_workflow.py "AI safety" --enable-console-exporters
#   python3 e2e_simple_workflow.py "AI safety" --stream --enable-console-exporters

import argparse
import asyncio
import json
import os
from typing import Annotated, cast

import httpx
from agent_framework import Agent, AgentResponse, AgentResponseUpdate, WorkflowBuilder, tool
from agent_framework.foundry import FoundryChatClient
from agent_framework.observability import configure_otel_providers, get_tracer
from azure.identity import AzureCliCredential
from dotenv import load_dotenv
from opentelemetry.trace import SpanKind
from opentelemetry.trace.span import format_trace_id
from pydantic import Field

load_dotenv()


RESEARCHER_PROMPT = """
You are a pragmatic web researcher.

Goal:
- Gather recent, credible sources about the topic.
- Return concise bullet insights and a small set of sources.

Rules:
- Prefer recency and credibility.
- Use only verifiable sources with valid URLs.
- Keep the summary short and focused.
- Use the web_search tool before answering.
- Return only information grounded in the tool results.

Input fields:
- topic
- context
- constraints

Output:
- summary bullets (4-6)
- sources (up to 3)
""".strip()


REVIEWER_PROMPT = """
You are a careful reviewer.

Goal:
- Review the researcher notes for accuracy and quality before writing.

Rules:
- Ensure claims map to sources.
- Flag weak evidence or missing support.
- Keep changes minimal and factual.

Output:
- review_notes list
- approved_research_notes
""".strip()


WRITER_PROMPT = """
You are a concise technical writer.

Goal:
- Draft a short response from approved research notes.

Rules:
- No fabrication.
- Use bracketed citations [1], [2], [3] aligned with sources.
- Keep it concise.
- Use Markdown sections exactly: Title, Introduction, Key Developments, Conclusion.

Output:
- Markdown draft with sections: Title, Introduction, Key Developments, Conclusion.
""".strip()


@tool(approval_mode="never_require")
def web_search(
    topic: Annotated[str, Field(description="Topic to search on the public internet.")],
    max_results: Annotated[
        int,
        Field(description="Maximum number of search-like results to return."),
    ] = 5,
) -> str:
    """Search DuckDuckGo Instant Answer API and return compact JSON payload."""
    url = "https://api.duckduckgo.com/"
    params = {
        "q": topic,
        "format": "json",
        "no_redirect": "1",
        "no_html": "1",
    }

    results: list[dict[str, str]] = []
    with httpx.Client(timeout=15.0) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()

    related = payload.get("RelatedTopics", [])
    for item in related:
        if len(results) >= max_results:
            break
        text = item.get("Text")
        first_url = item.get("FirstURL")
        if text and first_url:
            results.append(
                {
                    "title": text.split(" - ")[0][:120],
                    "url": first_url,
                    "source": "DuckDuckGo",
                    "snippet": text,
                }
            )

    return json.dumps({"topic": topic, "results": results}, indent=2)


def _read_required_env(var_name: str) -> str:
    value = os.getenv(var_name)
    if not value:
        raise ValueError(f"{var_name} is required")
    return value


def build_foundry_client() -> FoundryChatClient:
    project_endpoint = _read_required_env("FOUNDRY_PROJECTS_ENDPOINT")
    model = os.getenv("FOUNDRY_MODEL_DEPLOYMENT_NAME") or os.getenv("MAF_MODEL")
    if not model:
        raise ValueError("FOUNDRY_MODEL_DEPLOYMENT_NAME or MAF_MODEL is required")

    return FoundryChatClient(
        project_endpoint=project_endpoint,
        model=model,
        credential=AzureCliCredential(),
    )


def build_researcher_agent(client: FoundryChatClient) -> Agent:
    return Agent(
        client=client,
        name="researcher",
        instructions=RESEARCHER_PROMPT,
        tools=[web_search],
    )


def build_reviewer_agent(client: FoundryChatClient) -> Agent:
    return Agent(
        client=client,
        name="reviewer",
        instructions=REVIEWER_PROMPT,
    )


def build_writer_agent(client: FoundryChatClient) -> Agent:
    return Agent(
        client=client,
        name="writer",
        instructions=WRITER_PROMPT,
    )


def build_workflow(researcher: Agent, reviewer: Agent, writer: Agent):
    return (
        WorkflowBuilder(start_executor=researcher)
        .add_edge(researcher, reviewer)
        .add_edge(reviewer, writer)
        .build()
    )


def build_initial_input(
    topic: str, context: str | None = None, constraints: str | None = None
) -> str:
    context_value = context or "none"
    constraints_value = constraints or "none"
    return f"""
Topic: {topic}
Context: {context_value}
Constraints: {constraints_value}

Workflow requirements:
1. Researcher must search the web and return concise notes plus up to 3 sources.
2. Reviewer must validate evidence and provide approved research notes.
3. Writer must produce final markdown using citations from approved notes.
""".strip()


async def run_workflow(
    topic: str,
    context: str | None = None,
    constraints: str | None = None,
    stream: bool = False,
) -> None:
    client = build_foundry_client()
    researcher = build_researcher_agent(client)
    reviewer = build_reviewer_agent(client)
    writer = build_writer_agent(client)

    workflow = build_workflow(researcher, reviewer, writer)
    initial_input = build_initial_input(topic=topic, context=context, constraints=constraints)

    if stream:
        run_stream = workflow.run(initial_input, stream=True)
        async for event in run_stream:
            if event.type != "output":
                continue
            if not getattr(event.data, "text", ""):
                continue
            executor_id = getattr(event, "executor_id", None) or "agent"
            print(f"\n[stream:{executor_id}]\n{event.data.text}")
        events = await run_stream.get_final_response()
    else:
        events = await workflow.run(initial_input)

    outputs = cast(list[object], events.get_outputs())

    print("\n" + "=" * 80)
    print("WORKFLOW OUTPUTS")
    print("=" * 80)

    for idx, output in enumerate(outputs, start=1):
        author = _output_author(output, idx)
        print(f"\n--- Step {idx}: {author} ---")
        print(_output_text(output))

    print("\n" + "=" * 80)
    print("FINAL STATE")
    print("=" * 80)
    print(events.get_final_state())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run simple Researcher -> Reviewer -> Writer workflow"
    )
    parser.add_argument("topic", help="Research topic")
    parser.add_argument("--context", default=None, help="Optional context")
    parser.add_argument("--constraints", default=None, help="Optional constraints")
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Enable streaming workflow events",
    )
    parser.add_argument(
        "--enable-console-exporters",
        action="store_true",
        help="Enable console OTEL exporters (disabled by default)",
    )
    return parser.parse_args()


def _output_text(output: object) -> str:
    if isinstance(output, AgentResponse):
        return output.text or ""
    if isinstance(output, AgentResponseUpdate):
        return output.text or ""
    return str(output)


def _output_author(output: object, idx: int) -> str:
    if isinstance(output, AgentResponse):
        if output.messages:
            return output.messages[0].author_name or f"agent_{idx}"
        return f"agent_{idx}"
    if isinstance(output, AgentResponseUpdate):
        return getattr(output, "author_name", None) or f"agent_{idx}"
    return f"agent_{idx}"


async def main() -> None:
    args = parse_args()
    configure_otel_providers(
        enable_console_exporters=args.enable_console_exporters,
    )
    tracer = get_tracer()
    with tracer.start_as_current_span(
        "Simple Research Workflow Scenario", kind=SpanKind.CLIENT
    ) as span:
        print(f"Trace ID: {format_trace_id(span.get_span_context().trace_id)}")
        await run_workflow(
            topic=args.topic,
            context=args.context,
            constraints=args.constraints,
            stream=args.stream,
        )


if __name__ == "__main__":
    asyncio.run(main())
