SHELL := /bin/bash

IMAGE ?= researcher-agent
PORT ?= 8000
CONTAINER_NAME ?= researcher-agent-local

.PHONY: help
help:
	@echo "Targets:"
	@echo "  install       - Install package"
	@echo "  install-dev   - Install package with dev + test extras"
	@echo "  run           - Run uvicorn locally"
	@echo "  run-docker    - Build and run Docker container"
	@echo "  stop-docker   - Stop Docker container"
	@echo "  format        - Format code with black"
	@echo "  lint          - Lint code with ruff"
	@echo "  test          - Run tests"
	@echo "  build         - Build Docker image"
	@echo "  evals         - Run evaluations (placeholder)"

.PHONY: run
run:
	uvicorn app.main:create_app --host 0.0.0.0 --port $(PORT) --reload

.PHONY: install
install:
	python -m pip install -e .

.PHONY: install-dev
install-dev:
	python -m pip install -e .[dev,test]

.PHONY: run-docker
run-docker:
	docker build -t $(IMAGE) .
	docker run --rm --name $(CONTAINER_NAME) -p $(PORT):8000 --env-file .env $(IMAGE)

.PHONY: stop-docker
stop-docker:
	@docker rm -f $(CONTAINER_NAME) >/dev/null 2>&1 || true

.PHONY: format
format:
	black app tests

.PHONY: lint
lint:
	ruff check app tests

.PHONY: test
test:
	pytest -q

.PHONY: evals
evals:
	@echo "evals: add evaluation runner"

.PHONY: build
build:
	docker build -t $(IMAGE) .
