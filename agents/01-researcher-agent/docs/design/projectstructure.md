# Project Structure

```
agents/01-researcher-agent/
  app/
    main.py
    api/
      v1/
        routers/
          health.py
          research.py
        schemas/
          research.py
    modules/
      research/
        service.py
    core/
      config.py
      logging/
      middleware/
      observability/
      security/
        dependencies.py
        jwks.py
        models.py
        token_validator.py
    maf/
      clients.py
      prompts/
      tools.py
      workflows/
        research_workflow.py
  tests/
    test_health.py
    test_research_routes.py
    test_research_service.py
    test_auth.py
    test_smoke_live.py
  docs/
    design/
```

Notes:

- Each agent is self-contained and independently deployable.
- FastAPI entrypoint: `app/main.py`.
- Versioned HTTP surface: `app/api/v1/*`.
- Business logic for research flow lives in `app/modules/research`.
- MAF orchestration lives in `app/maf`.
