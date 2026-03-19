# Development

This page covers how to set up a development environment, run the test suites, and understand the project structure.

## Prerequisites

- **Python 3.11+** with [uv](https://docs.astral.sh/uv/getting-started/installation/)
- **git**
- [just](https://github.com/casey/just) (recommended — all commands below have `just` equivalents)

## Project Structure

```
specmap/
├── core/                  # Python: core library, MCP server, CLI
│   ├── src/specmap/       # Source code
│   │   ├── indexer/       # Hashing, parsing, code analysis, validation
│   │   ├── state/         # Models, specmap file I/O, relocator
│   │   ├── llm/           # LLM client, prompts, schemas
│   │   ├── tools/         # MCP tool implementations
│   │   ├── mcp/           # MCP server entrypoint
│   │   └── cli/           # Typer CLI entrypoint + commands
│   ├── tests/             # Unit tests (pytest)
│   └── pyproject.toml
├── tests/                 # Functional test suite
│   ├── conftest.py        # Session fixtures
│   ├── harness/           # Test infrastructure
│   └── scenarios/         # End-to-end test scenarios
├── docs/                  # MkDocs documentation
├── justfile               # Task runner
└── mkdocs.yml
```

## Installing Dependencies

```bash
just mcp-install   # Python deps (core library + MCP server + CLI + test deps)
```

## Running Tests

Specmap has two test layers:

### Unit Tests

Focused on individual components — hashing, parsing, models, file I/O, validation.

```bash
just mcp-test
```

Run with coverage:

```bash
just mcp-test-cov
```

### Functional Tests

End-to-end scenarios that exercise real spec-driven workflows: mapping code to specs, detecting staleness, reindexing, validating via CLI — all with deterministic LLM mocks.

```bash
just functional-test           # All 32 scenarios (~5s)
just functional-test-fast      # Skip @slow tests
just functional-test -v        # Verbose per-test output
just functional-test -x        # Stop on first failure
```

The functional tests create temporary git repos, mock `litellm.acompletion`, call MCP tools, and run the CLI — verifying the full pipeline end-to-end.

### All Tests

```bash
just test       # Unit tests only
just test-all   # Unit + functional tests
```

## Functional Test Architecture

### Five-Layer Harness

```
tests/
├── conftest.py              # Session fixtures: CLI runner, LLM mock, temp repos
├── harness/
│   ├── repo.py              # GitRepo: temp repos, file ops, git ops
│   ├── llm_mock.py          # Mock litellm.acompletion + response builders
│   ├── cli.py               # Run Python CLI via subprocess
│   ├── assertions.py        # Domain-specific assertion helpers
│   ├── spec_content.py      # Reusable spec markdown constants
│   └── code_content.py      # Reusable code file constants
└── scenarios/
    ├── test_greenfield.py   # New repo: spec → code → map → validate → check
    ├── test_iterative.py    # Edit code → stale → reindex → re-map
    ├── test_spec_evolution.py  # Edit spec → relocation strategies → stale
    ├── test_branch.py       # Feature branches, cumulative diffs
    ├── test_coverage.py     # Threshold enforcement, edge cases
    ├── test_config.py       # Custom patterns, env vars, ignore rules
    ├── test_errors.py       # Empty repos, missing files, unicode, deep headings
    └── test_cross_component.py  # End-to-end hash compatibility
```

### LLM Mock Strategy

Tests mock `litellm.acompletion` — not `LLMClient.complete` — so the full LLM client stack is exercised: retry logic, JSON parsing, Pydantic validation, and token tracking.

The `LLMMockRegistry` dispatches responses by call type (mapping vs. reindex) using matcher functions:

```python
# Register a mock response for mapping calls
mapping = build_mapping_for_spec(
    AUTH_SPEC, "Token Storage", "docs/auth-spec.md",
    ["Authentication", "Token Storage"],
)
llm_mock.on_mapping(MappingResponse(mappings=[mapping]))

# Register a mock response for reindex calls
reindex_resp = build_reindex_result(
    UPDATED_SPEC, "Token Storage", "docs/auth-spec.md",
    ["Authentication", "Token Storage"],
)
llm_mock.on_reindex(reindex_resp)
```

The `build_mapping_for_spec` helper computes correct `span_offset` and `span_length` by parsing the spec content and finding the heading — ensuring that `hash_span(content, offset, length)` in the mapper produces a hash that matches what the validator computes.

### Scenario Repo Setup

Each test gets a fresh temporary git repo with `main` and `feature/test` branches. Spec files are committed to `main` and merged into the feature branch so they exist in the working tree but don't appear in `git diff main...HEAD`:

```python
def setup_spec_on_main(repo, spec_path, content):
    repo.git_checkout("main")
    repo.write_file(spec_path, content)
    repo.git_add(spec_path)
    repo.git_commit(f"Add {spec_path}")
    repo.git_checkout("feature/test")
    repo.git_merge("main")
```

## Linting and Formatting

```bash
just mcp-lint    # ruff check
just mcp-fmt     # ruff format
just lint        # All lints
```

## Documentation

Docs use [MkDocs Material](https://squidfunnel.com/mkdocs-material/) with mike for versioning.

```bash
just docs-install   # One-time: install mkdocs into docs/.venv
just docs-serve     # Live-reload dev server at localhost:8000
just docs-build     # Build static site (strict mode)
```

## Code Hash Normalization

Code hashes strip trailing newlines before hashing. This ensures consistent hashes regardless of whether files end with a trailing newline:

```python
def hash_code_lines(file_content, start_line, end_line):
    lines = file_content.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    selected = lines[start_line - 1 : end_line]
    return hash_content("\n".join(selected))
```

The `split("\n")` → select → `join("\n")` pattern naturally normalizes trailing newlines. This contract is verified by unit tests and functional tests.

See [Hashing & Reindexing](concepts/hashing.md) for the full hash hierarchy.
