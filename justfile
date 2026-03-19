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

# --- Combined ---

# Run all tests
test: mcp-test cli-test

# Run all lints
lint: mcp-lint cli-vet
