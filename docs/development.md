# Development

Everything you need to clone and run specmap locally.

## Prerequisites

| Tool | Purpose | Install |
|------|---------|---------|
| Python 3.11+ | Core library, MCP server, CLI, API server | System package manager |
| [uv](https://docs.astral.sh/uv/) | Python package manager | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js 20+ | React frontend | System package manager |
| [just](https://github.com/casey/just) | Task runner | `cargo install just` or [system packages](https://github.com/casey/just#installation) |
| git | Version control | System package manager |

## Clone and Install

```bash
git clone https://github.com/jdraines/specmap.git
cd specmap
just mcp-install     # Python deps (core library + MCP server + CLI + API server + test deps)
just web-install     # Node deps (React frontend)
```

## Running the Web UI

The web UI needs a forge token to fetch repo data on your behalf. Specmap auto-detects the forge provider (GitHub or GitLab) from your `git remote origin`.

### 1. Set a personal access token

**GitHub** — use any of these methods (checked in order):

1. Set `GITHUB_TOKEN` (or `GH_TOKEN`) environment variable
2. Have `gh` CLI authenticated (`gh auth login`) — specmap falls back to `gh auth token`

The token needs `repo` scope for private repositories, or no scope for public-only.

**GitLab** — use any of these methods (checked in order):

1. Set `GITLAB_TOKEN` environment variable
2. Have `glab` CLI authenticated — specmap falls back to `glab config get token`

The token needs `read_api` and `read_repository` scopes.

### 2. Configure environment (optional)

```bash
cp .env.example .env
```

For PAT mode (the default), the only thing you might need to set is `CORS_ORIGIN`:

```bash
CORS_ORIGIN=http://localhost:5173
```

Session secrets are auto-generated if not provided.

#### OAuth mode (enterprise)

If your organization restricts PATs, you can configure OAuth instead:

**GitHub** — Go to [github.com/settings/developers](https://github.com/settings/developers) > **OAuth Apps** > **New OAuth App**:

| Field | Value |
|-------|-------|
| Application name | Specmap (dev) |
| Homepage URL | `http://localhost:8080` |
| Authorization callback URL | `http://localhost:8080/api/v1/auth/callback/github` |

**GitLab** — Go to your GitLab instance > **Preferences** > **Applications** > **New Application**:

| Field | Value |
|-------|-------|
| Name | Specmap (dev) |
| Redirect URI | `http://localhost:8080/api/v1/auth/callback/gitlab` |
| Scopes | `read_api`, `read_repository` |

Then set the client credentials in `.env`:

```bash
GITHUB_CLIENT_ID=<from step above>
GITHUB_CLIENT_SECRET=<from step above>
# or for GitLab:
GITLAB_CLIENT_ID=<from step above>
GITLAB_CLIENT_SECRET=<from step above>
```

### 3. Start services

```bash
just dev    # Runs API server + Vite dev server in one command
```

This starts both processes in parallel (API on `:8080` with auto-reload, Vite on `:5173`). Open [http://localhost:5173](http://localhost:5173). In PAT mode with a valid token, the dashboard loads immediately. In OAuth mode, click the sign-in button.

You can also run them in separate terminals if you prefer:

```bash
# Terminal 1: Python API server
just serve         # or: just serve-dev (auto-reload)

# Terminal 2: React frontend
just web-dev
```

## Project Structure

```
specmap/
├── core/                  # Python: core library, MCP server, CLI, API server
│   ├── src/specmap/       # Source code
│   │   ├── indexer/       # Diff analysis, annotation engine, diff optimizer
│   │   ├── state/         # Models, specmap file I/O
│   │   ├── llm/           # LLM client, prompts, schemas
│   │   ├── tools/         # MCP tool implementations
│   │   ├── mcp/           # MCP server entrypoint
│   │   ├── cli/           # Typer CLI entrypoint + commands
│   │   └── server/        # FastAPI server (auth, forge API, SQLite)
│   ├── tests/             # Unit tests (pytest)
│   └── pyproject.toml
├── web/                   # React frontend
│   ├── src/
│   │   ├── api/           # TypeScript API client
│   │   ├── stores/        # Zustand state management
│   │   ├── hooks/         # Custom React hooks
│   │   ├── components/    # React components
│   │   └── pages/         # Route pages
│   └── vite.config.ts
├── tests/                 # Functional test suite
│   ├── conftest.py        # Session fixtures
│   ├── harness/           # Test infrastructure
│   └── scenarios/         # End-to-end test scenarios
├── docs/                  # MkDocs documentation
├── justfile               # Task runner
└── mkdocs.yml
```

## Running Tests

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

End-to-end scenarios that exercise real spec-driven workflows: annotating code with spec references, verifying annotations, and validating via CLI -- all with deterministic LLM mocks.

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

## Linting and Formatting

```bash
just mcp-lint      # ruff check
just mcp-fmt       # ruff format
just web-typecheck # tsc --noEmit
just lint          # All lints (ruff + tsc)
```

## Documentation

Docs use [MkDocs Material](https://squidfunnel.com/mkdocs-material/) with mike for versioning.

```bash
just docs-install   # One-time: install mkdocs into docs/.venv
just docs-serve     # Live-reload dev server at localhost:8000
just docs-build     # Build static site (strict mode)
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
    ├── test_greenfield.py       # New repo: spec + code -> annotate -> validate
    ├── test_iterative.py        # Edit code -> re-annotate with incremental diff
    ├── test_cross_component.py  # Cross-component annotation scenarios
    ├── test_branch.py           # Feature branches, cumulative diffs
    ├── test_config.py           # Custom patterns, env vars, ignore rules
    └── test_errors.py           # Empty repos, missing files, unicode, deep headings
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

## Troubleshooting

**"CORS error in browser console"** -- Check that `CORS_ORIGIN` in `.env` matches the Vite dev server URL exactly (`http://localhost:5173`).

**"Empty annotations on PR page"** -- The `.specmap/{branch}.json` file must be committed and pushed to the PR branch. The API fetches it from the forge at the PR's head SHA.

**"OAuth callback error"** -- Verify the callback URL in your OAuth App settings matches `BASE_URL` + `/api/v1/auth/callback/{provider}` exactly.

**"No token found"** -- In PAT mode, ensure your token is set via env var or CLI tool. You can also enter it manually in the web UI login page.
