# Specmap task runner
set dotenv-load

# Default: show available commands
default:
    @just --list

# --- Python Core (MCP server, CLI, shared library) ---

# Install Python dependencies
install:
    uv sync --extra dev

# Run MCP server (stdio mode)
mcp-run:
    uv run python -m specmap.mcp

# Run Python unit tests
test *ARGS:
    uv run pytest {{ARGS}}

# Run Python tests with coverage
test-cov:
    uv run pytest --cov=specmap --cov-report=term-missing

# Lint Python
lint-py:
    uv run ruff check src/ tests/

# Format Python
fmt:
    uv run ruff format src/ tests/

# --- CLI ---

# Run CLI command
cli-run *ARGS:
    uv run python -m specmap.cli {{ARGS}}

# --- Server ---

# Run API server
serve:
    uv run specmap serve

# Run API server with auto-reload
serve-dev:
    uv run specmap serve --reload

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
    uv run pytest tests/scenarios -o asyncio_mode=auto {{ARGS}}

# Run fast functional tests (skip slow)
functional-test-fast *ARGS:
    uv run pytest tests/scenarios -o asyncio_mode=auto -m "not slow" {{ARGS}}

# --- Versioning ---

# Show current version
versions:
    @echo "specmap: $(sed -n 's/^version = \"\(.*\)\"/\1/p' pyproject.toml)"

# Bump version (updates pyproject.toml)
version VERSION:
    sed -i 's/^version = ".*"/version = "{{VERSION}}"/' pyproject.toml
    @echo "specmap → {{VERSION}}"

# Bump version, commit, tag, and push (triggers PyPI publish via GH Actions)
release VERSION: (version VERSION)
    git add pyproject.toml
    git commit -m "Release {{VERSION}}"
    git tag v{{VERSION}}
    git push && git push --tags
    @echo "Released v{{VERSION}} — GitHub Actions will publish to PyPI"

# --- Deployment ---

# Build Docker image
image-build:
    docker build -t specmap:latest .

# --- Build ---

# Build Python wheel with bundled frontend
build: web-build
    uv build

# Publish to PyPI (builds first, asks for confirmation)
publish: build
    #!/usr/bin/env bash
    set -euo pipefail
    version=$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml)
    echo "About to publish specmap v${version} to PyPI"
    echo "Files:"
    ls -lh dist/specmap-${version}*
    echo ""
    read -p "Publish to PyPI? [y/N] " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        echo "Aborted."
        exit 1
    fi
    uvx twine upload --repository pypi dist/specmap-${version}*
    echo "Published specmap v${version} to PyPI"

# Publish to TestPyPI (builds first, asks for confirmation)
publish-test: build
    #!/usr/bin/env bash
    set -euo pipefail
    version=$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml)
    echo "About to publish specmap v${version} to TestPyPI"
    read -p "Publish to TestPyPI? [y/N] " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        echo "Aborted."
        exit 1
    fi
    uvx twine upload --repository testpypi dist/specmap-${version}*
    echo "Published specmap v${version} to TestPyPI"

# Run full dev stack (API + Vite dev server)
dev:
    #!/usr/bin/env bash
    trap 'kill 0' EXIT
    CORS_ORIGIN=http://localhost:5173 uv run specmap serve --reload --no-open &
    cd web && npm run dev &
    wait

# --- Combined ---

# Run all tests including functional
test-all: test functional-test

# Run all lints
lint: lint-py web-typecheck
