SHELL := /bin/bash

.PHONY: help
help:
	@echo "Targets:"
	@echo "  agent-test    Run tests for 01-researcher-agent"
	@echo "  agent-run     Run 01-researcher-agent locally"

.PHONY: agent-test
agent-test:
	$(MAKE) -C agents/01-researcher-agent test

.PHONY: agent-run
agent-run:
	$(MAKE) -C agents/01-researcher-agent run
