SHELL := /bin/bash
.DEFAULT_GOAL := help

.PHONY: help publish

help: ## List available targets.
	@echo "Available targets:"
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_-]+:.*##/ {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

publish: ## Load UV_PUBLISH_TOKEN from .env, then clean dist/, run uv build and uv publish.
	@test -f .env || (echo ".env not found. Create it with UV_PUBLISH_TOKEN=..."; exit 1)
	@set -a; source .env; set +a; \
		rm -rf dist && \
		uv build && \
		uv publish
