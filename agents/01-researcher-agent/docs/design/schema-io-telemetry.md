# Research Schema I/O and Telemetry Map

## Request Contract

Source: app/api/v1/schemas/research.py

- topic (required string)
- context (optional string)
- constraints (optional string)

## Response Contract

Source: app/api/v1/schemas/research.py

- summary (string)
- draft (string)
- review (string)

## Transformation Path

1. Router boundary

Source: app/api/v1/routers/research.py

- Accepts request schema and emits full-content input telemetry (dev mode).
- Adds span attributes:
  - topic.length
  - context.present
  - context.length
  - has_constraints
  - constraints.length
  - stream
- Emits event: research.schema.input
  - topic, context, constraints

2. Service boundary

Source: app/modules/research/service.py

- Passes request into workflow.
- For non-streaming responses, emits full-content output event:
  - research.service.output
  - summary, draft, review, summary.length, draft.length, review.length, stream
- For streaming responses, emits sparse stream lifecycle events:
  - research.service.stream.progress (first chunk and periodic checkpoints)
  - research.service.stream.completed (end summary)
  - research.service.stream.failed (error summary)
  - fields include chunk_index, dict_chunks, output_chunks and completion/error markers

3. Workflow boundary

Source: app/maf/workflows/research_workflow.py

- Builds prompt from request fields via app/maf/prompts/prompts.py.
- Runs chain: ResearcherAgent -> ReviewerAgent -> WriterAgent.
- Emits node-style milestone events for parity with lower noise:
  - research.workflow.node.invoked
  - research.workflow.node.first_output
  - research.workflow.node.progress (periodic)
  - research.workflow.node.completed
  - research.workflow.node.summary
  - node names: node.researcher, node.reviewer, node.writer
- Maps executor outputs into response contract fields.
- Emits workflow output metadata event:
- Emits workflow output event:
- research.workflow.outputs
- summary.length
- draft.length
- review.length
- summary.truncated
- summary.source (writer, reviewer, researcher, ordered_fallback)
- fallback.used
- stream (stream path only)

4. Tool boundary

Source: app/maf/tools.py

- web_search emits metadata-only event:
- web_search emits full dev-content event:
- research.tool.web_search
- topic.length
- topic
- max_results
- results.count
- results.payload
- http.status_code
- http.status_class
- parse.success

## Privacy and Data Handling

This telemetry configuration is intentionally dev-focused and captures sensitive prompt/response content for trace debugging.
Do not use this profile unchanged for production environments.

## Why This Matters

- Makes schema usage observable without exposing user payload content.
- Enables later tuning of output mapping and truncation behavior.
- Supports strict deployment telemetry validation for requests, dependencies, traces, and custom metrics.
