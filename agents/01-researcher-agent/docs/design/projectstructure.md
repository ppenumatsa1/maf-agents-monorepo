# Project Structure

```
agents/01-researcher-agent/
  app/
    core/
      logging/
      middleware/
      observability/
    domain/
      routes/
      schemas/
      services/
      repo/
    maf/
  tests/
  docs/
    design/
```

Notes:

- Each agent is self-contained and independently deployable.
- FastAPI entrypoint: app/main.py
- Workflow stubs: app/maf/workflow.py
