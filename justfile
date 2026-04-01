# Specmap task runner
set dotenv-load

# Default: show available commands
default:
    @just --list

# --- Python Core (MCP server, CLI, shared library) ---

# Install Python dependencies
mcp-install:
    cd core && uv sync

# Run MCP server (stdio mode)
mcp-run:
    cd core && uv run python -m specmap.mcp

# Run Python unit tests
mcp-test *ARGS:
    cd core && uv run pytest {{ARGS}}

# Run Python tests with coverage
mcp-test-cov:
    cd core && uv run pytest --cov=specmap --cov-report=term-missing

# Lint Python
mcp-lint:
    cd core && uv run ruff check src/ tests/

# Format Python
mcp-fmt:
    cd core && uv run ruff format src/ tests/

# --- CLI ---

# Run CLI command
cli-run *ARGS:
    cd core && uv run python -m specmap.cli {{ARGS}}

# --- Go API Server ---

# Build API binary
api-build:
    cd api && go build -ldflags "-X main.Version=$(cat VERSION)" -o specmap-api ./cmd/api

# Run API server
api-run:
    cd api && go run ./cmd/api

# Run Go tests
api-test *ARGS:
    cd api && go test ./... {{ARGS}}

# Vet Go code
api-vet:
    cd api && go vet ./...

# Start local dev services (Postgres)
dev-up:
    docker compose up -d

# Stop local dev services
dev-down:
    docker compose down

# --- Web Frontend ---

# Install web dependencies
web-install:
    cd web && npm install

# Run web dev server
web-dev:
    cd web && npm run dev

# Build web for production
web-build:
    cd web && npm run build

# TypeScript type check
web-typecheck:
    cd web && npx tsc --noEmit

# --- Documentation ---

# Install docs dependencies
docs-install:
    uv venv docs/.venv && uv pip install -r docs/requirements.txt --python docs/.venv/bin/python

# Serve docs locally
docs-serve:
    docs/.venv/bin/mkdocs serve

# Build docs (strict mode)
docs-build:
    docs/.venv/bin/mkdocs build --strict

# Deploy docs version (e.g., just docs-deploy 0.1)
docs-deploy VERSION:
    docs/.venv/bin/mike deploy --push --update-aliases {{VERSION}} latest

# List deployed doc versions
docs-versions:
    docs/.venv/bin/mike list

# --- Functional Tests ---

# Run functional test suite
functional-test *ARGS:
    cd core && uv run pytest ../tests -o asyncio_mode=auto {{ARGS}}

# Run fast functional tests (skip slow)
functional-test-fast *ARGS:
    cd core && uv run pytest ../tests -o asyncio_mode=auto -m "not slow" {{ARGS}}

# --- Versioning ---

# Show current versions
versions:
    @echo "core: $(sed -n 's/^version = \"\(.*\)\"/\1/p' core/pyproject.toml)"
    @echo "web:  $(cat api/VERSION)"

# Bump core version (updates pyproject.toml)
core-version VERSION:
    sed -i 's/^version = ".*"/version = "{{VERSION}}"/' core/pyproject.toml
    @echo "core → {{VERSION}}. Tag with: git tag core/v{{VERSION}}"

# Bump web version (updates api/VERSION)
web-version VERSION:
    printf '%s\n' '{{VERSION}}' > api/VERSION
    @echo "web → {{VERSION}}. Tag with: git tag web/v{{VERSION}}"

# --- Combined ---

# Run all unit tests
test: mcp-test api-test

# Run all tests including functional
test-all: mcp-test api-test functional-test

# Run all lints
lint: mcp-lint api-vet web-typecheck
