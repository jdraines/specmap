# Development

This page covers how to set up a development environment, run the test suites, and understand the project structure.

## Prerequisites

- **Python 3.11+** with [uv](https://docs.astral.sh/uv/getting-started/installation/)
- **git**
- [just](https://github.com/casey/just) (recommended -- all commands below have `just` equivalents)

## Project Structure

```
specmap/
├── core/                  # Python: core library, MCP server, CLI
│   ├── src/specmap/       # Source code
│   │   ├── annotator/     # Diff analysis, annotation engine, diff optimizer
│   │   ├── state/         # Models, specmap file I/O
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

Focused on individual components -- annotation engine, diff optimizer, models, file I/O, code analyzer.

```bash
just mcp-test
```

Run with coverage:

```bash
just mcp-test-cov
```

### Functional Tests

End-to-end scenarios that exercise real spec-driven workflows: annotating code with spec references, verifying annotations, computing coverage, enforcing thresholds via CLI -- all with deterministic LLM mocks.

```bash
just functional-test           # All scenarios (~5s)
just functional-test-fast      # Skip @slow tests
just functional-test -v        # Verbose per-test output
just functional-test -x        # Stop on first failure
```

The functional tests create temporary git repos, mock `litellm.acompletion`, call MCP tools, and run the CLI -- verifying the full pipeline end-to-end.

### All Tests

```bash
just test       # Unit tests only
just test-all   # Unit + functional tests
```

## Functional Test Architecture

### Multi-Layer Harness

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
    ├── test_greenfield.py   # New repo: spec + code -> annotate -> validate -> check
    ├── test_iterative.py    # Edit code -> re-annotate with incremental diff
    ├── test_spec_evolution.py  # Edit spec -> annotations regenerated
    ├── test_branch.py       # Feature branches, cumulative diffs
    ├── test_coverage.py     # Threshold enforcement, edge cases
    ├── test_config.py       # Custom patterns, env vars, ignore rules
    ├── test_errors.py       # Empty repos, missing files, unicode, deep headings
    └── test_optimization.py # Incremental diff: keep/shift/regenerate classification
```

### LLM Mock Strategy

Tests mock `litellm.acompletion` -- not `LLMClient.complete` -- so the full LLM client stack is exercised: retry logic, JSON parsing, Pydantic validation, and token tracking.

The `LLMMockRegistry` dispatches responses by call type using matcher functions:

```python
# Register a mock response for annotation calls
annotation_resp = build_annotation_response(
    file="auth/session.go",
    start_line=15, end_line=42,
    description="Implements JWT session tokens [1].",
    refs=[build_spec_ref(1, "docs/auth-spec.md", "Authentication > Token Storage", 5)],
)
llm_mock.on_annotate(AnnotationResponse(annotations=[annotation_resp]))
```

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
