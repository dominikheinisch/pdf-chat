UV_IMAGE := ghcr.io/astral-sh/uv:0.13.0-python3.13-trixie-slim

export UID := $(shell id -u)
export GID := $(shell id -g)

# Resource caps for compose.yaml, scaled to this host: 70% of RAM, all cores but two.
# APP_MEM_LIMIT / APP_CPUS in .env take precedence; empty (no /proc) means its fallback.
export AUTO_MEM_LIMIT := $(shell awk '/^MemTotal/ {printf "%dm", $$2 * 0.7 / 1024}' /proc/meminfo 2>/dev/null)
export AUTO_CPUS := $(shell n=$$(nproc 2>/dev/null) && echo $$((n > 2 ? n - 2 : 1)))

# One-off app container with the repo bind-mounted: tools see current code and write back.
# --no-deps: tools don't need the database.
TOOL := docker compose run --rm --build --no-deps -v "$(CURDIR)":/app app
# Plain uv image: works before uv.lock exists; --no-sync keeps a venv out of the repo.
UV := docker run --rm -u $(UID):$(GID) -e UV_CACHE_DIR=/tmp/uv-cache \
	-v "$(CURDIR)":/app -w /app $(UV_IMAGE) uv

.DEFAULT_GOAL := help
.PHONY: help build run dev down reset test test-integration lint shell lock add

help: ## Show this help
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-17s %s\n", $$1, $$2}'

build: ## Build the app image
	docker compose build

run: ## Start the chat UI on http://localhost:8001 (APP_PORT=... to change)
	docker compose up --build

dev: ## Sync + restart on code changes; meant for long-running apps
	docker compose up --build --watch

down: ## Stop and remove containers (chat history is kept)
	docker compose down --remove-orphans

reset: ## Stop and delete all chats and documents (needed after a schema change)
	docker compose down --remove-orphans --volumes

test: ## Run unit tests
	$(TOOL) pytest $(ARGS)

test-integration: ## Run integration tests against Postgres
	docker compose run --rm --build -v "$(CURDIR)":/app app pytest -m integration $(ARGS)

lint: ## Fix lint issues, then format (fails if unfixable issues remain)
	$(TOOL) sh -c 'ruff check --fix; rc=$$?; ruff format && exit $$rc'

shell: ## Open a bash shell in the app container
	$(TOOL) bash

lock: ## Resolve dependencies into uv.lock
	$(UV) lock

add: ## Add a dependency: make add PKG=httpx [GROUP=dev]
	$(UV) add --no-sync $(if $(GROUP),--group $(GROUP)) $(PKG)
