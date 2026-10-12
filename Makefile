UV_IMAGE := ghcr.io/astral-sh/uv:0.13.0-python3.13-trixie-slim

export UID := $(shell id -u)
export GID := $(shell id -g)

# One-off app container with the repo bind-mounted: tools see current code and write back.
TOOL := docker compose run --rm --build -v "$(CURDIR)":/app app
# Plain uv image: works before uv.lock exists; --no-sync keeps a venv out of the repo.
UV := docker run --rm -u $(UID):$(GID) -e UV_CACHE_DIR=/tmp/uv-cache \
	-v "$(CURDIR)":/app -w /app $(UV_IMAGE) uv

.DEFAULT_GOAL := help
.PHONY: help build run dev down test lint shell lock add

help: ## Show this help
	@grep -E '^[a-z]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-6s %s\n", $$1, $$2}'

build: ## Build the app image
	docker compose build

run: ## Run the app once (ARGS="..." are passed to main.py)
	docker compose run --rm --build app python src/main.py $(ARGS)

dev: ## Sync + restart on code changes; meant for long-running apps
	docker compose up --build --watch

down: ## Stop and remove containers
	docker compose down --remove-orphans

test: ## Run pytest
	$(TOOL) pytest

lint: ## Fix lint issues, then format (fails if unfixable issues remain)
	$(TOOL) sh -c 'ruff check --fix; rc=$$?; ruff format && exit $$rc'

shell: ## Open a bash shell in the app container
	$(TOOL) bash

lock: ## Resolve dependencies into uv.lock
	$(UV) lock

add: ## Add a dependency: make add PKG=httpx [GROUP=dev]
	$(UV) add --no-sync $(if $(GROUP),--group $(GROUP)) $(PKG)
