SHELL := /bin/bash

AGENT ?= 01-researcher-agent
ARGS ?=
PORT ?= 8000
REQUIRE_AUTH ?= false

.PHONY: help install install-dev run run-docker stop-docker format lint test verify smoke test-smoke verify-deployment build evals observability-suite
help:
	@echo "Targets:"
	@echo "  install install-dev run run-docker stop-docker format lint test verify smoke test-smoke verify-deployment build evals observability-suite"
	@echo ""
	@echo "Usage examples:"
	@echo "  make test"
	@echo "  make run PORT=18080 REQUIRE_AUTH=false"
	@echo "  make verify-deployment ARGS='--env local --base-url http://127.0.0.1:18080'"
	@echo "  make verify-deployment ARGS='--env azure --base-url https://<fqdn> --tenant-id <id> --client-id <id> --client-secret <secret> --scope <scope>'"

install install-dev run run-docker stop-docker format lint test verify smoke test-smoke verify-deployment build evals:
	$(MAKE) -C agents/$(AGENT) $@ ARGS="$(ARGS)" PORT="$(PORT)" REQUIRE_AUTH="$(REQUIRE_AUTH)"

observability-suite:
	bash scripts/kusto/run-observability-suite.sh $(ARGS)
