# Specmap task runner

# Default: show available commands
default:
    @just --list

# --- Python MCP Server ---

# Install Python dependencies
mcp-install:
    cd mcp && uv sync

# Run MCP server (stdio mode)
mcp-run:
    cd mcp && uv run python -m specmap_mcp

# Run Python tests
mcp-test *ARGS:
    cd mcp && uv run pytest {{ARGS}}

# Run Python tests with coverage
mcp-test-cov:
    cd mcp && uv run pytest --cov=specmap_mcp --cov-report=term-missing

# Lint Python
mcp-lint:
    cd mcp && uv run ruff check src/ tests/

# Format Python
mcp-fmt:
    cd mcp && uv run ruff format src/ tests/

# --- Go CLI ---

# Build CLI binary
cli-build:
    cd cli && go build -o specmap .

# Run Go tests
cli-test *ARGS:
    cd cli && go test ./... {{ARGS}}

# Vet Go code
cli-vet:
    cd cli && go vet ./...

# Run CLI command
cli-run *ARGS:
    cd cli && go run . {{ARGS}}

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

# --- Combined ---

# Run all tests
test: mcp-test cli-test

# Run all lints
lint: mcp-lint cli-vet
