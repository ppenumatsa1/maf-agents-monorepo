SHELL := /bin/bash
PYTHON ?= python3
PORT ?= 8000
IMAGE ?= researcher-agent
CONTAINER_NAME ?= researcher-agent-local
REQUIRE_AUTH ?= false
ENABLE_TELEMETRY ?= false
COMPOSE ?= docker compose
COMPOSE_FILE ?= docker-compose.yml
COMPOSE_ARGS ?= -f $(COMPOSE_FILE)
ARGS ?=

.PHONY: help setup deps precommit run up up-build down logs lint format format-check test smoke test-smoke evals verify verify-deployment build run-docker stop-docker install install-dev

help: ## Display available targets
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*## "}; {printf "  %-16s %s\n", $$1, $$2}'

setup: deps precommit ## Bootstrap local developer environment

deps: ## Install Python dependencies into the active environment
	$(PYTHON) -m pip install '.[dev,test]'
	rm -rf build

precommit: ## Install git hooks for lint/format checks
	@if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then \
		pre-commit install; \
	else \
		echo "Skipping pre-commit install (not inside a git repository)."; \
	fi

run: ## Run uvicorn locally (auth and telemetry export disabled)
	REQUIRE_AUTH=false ENABLE_TELEMETRY=false $(PYTHON) -m uvicorn app.main:create_app --factory --reload --port $(PORT)

up: ## Start Docker container from existing image
	CONTAINER_NAME=$(CONTAINER_NAME) IMAGE=$(IMAGE) PORT=$(PORT) REQUIRE_AUTH=false ENABLE_TELEMETRY=false $(COMPOSE) $(COMPOSE_ARGS) up -d

up-build: ## Rebuild image and start Docker container
	CONTAINER_NAME=$(CONTAINER_NAME) IMAGE=$(IMAGE) PORT=$(PORT) REQUIRE_AUTH=false ENABLE_TELEMETRY=false $(COMPOSE) $(COMPOSE_ARGS) up -d --build

down: ## Stop Docker container
	CONTAINER_NAME=$(CONTAINER_NAME) IMAGE=$(IMAGE) PORT=$(PORT) REQUIRE_AUTH=$(REQUIRE_AUTH) ENABLE_TELEMETRY=$(ENABLE_TELEMETRY) $(COMPOSE) $(COMPOSE_ARGS) down --remove-orphans

logs: ## Tail Docker Compose logs
	CONTAINER_NAME=$(CONTAINER_NAME) IMAGE=$(IMAGE) PORT=$(PORT) REQUIRE_AUTH=$(REQUIRE_AUTH) ENABLE_TELEMETRY=$(ENABLE_TELEMETRY) $(COMPOSE) $(COMPOSE_ARGS) logs -f --tail 200

build: ## Build Docker image via Compose
	CONTAINER_NAME=$(CONTAINER_NAME) IMAGE=$(IMAGE) PORT=$(PORT) REQUIRE_AUTH=$(REQUIRE_AUTH) ENABLE_TELEMETRY=$(ENABLE_TELEMETRY) $(COMPOSE) $(COMPOSE_ARGS) build

format: ## Run isort followed by Black
	./scripts/format.sh

format-check: ## Check formatting with Black
	black --check app tests

lint: ## Run Ruff checks
	./scripts/lint.sh

test: ## Execute pytest suite
	./scripts/test.sh

smoke: ## Execute smoke pytest against SMOKE_BASE_URL
	REQUIRE_AUTH=false SMOKE_BASE_URL=http://localhost:$(PORT) pytest tests/test_smoke_live.py -q

test-smoke: ## Execute local smoke tests with auth disabled
	./scripts/test_smoke.sh

evals: ## Run evaluations
	@echo "evals: add evaluation runner"

verify: ## Run post-deployment verification checks
	bash ./scripts/verify_deployment.sh $(ARGS)

verify-deployment: verify ## Compatibility alias for verify
