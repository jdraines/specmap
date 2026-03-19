# Specmap task runner

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

# --- Combined ---

# Run all unit tests
test: mcp-test

# Run all tests including functional
test-all: mcp-test functional-test

# Run all lints
lint: mcp-lint
