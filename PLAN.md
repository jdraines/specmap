# Specmap Implementation Plan

## Context

AI coding agents generate large volumes of code, but humans still need to review it. Development is increasingly spec-driven — agents write plans/specs, then generate code from them. Specmap bridges this gap by generating LLM-powered annotations that link code changes to spec intent, so reviewers can see *why* code exists alongside *what* it does. Reviewers answer two questions: Is this intent what we want? Does the code match the intent?

This is a greenfield project targeting startup viability. Phase 1 (MCP server + CLI) is standalone and immediately useful without any server infrastructure.

---

## Architecture Overview

```
┌─────────────────┐    ┌──────────────────────────┐    ┌──────────────────┐
│   React SPA     │    │   Python API Server      │    │   SQLite         │
│   (Vite)        │◄──►│   (FastAPI / Uvicorn)    │◄──►│                  │
│                 │    │                          │    │                  │
└─────────────────┘    └──────────┬───────────────┘    └──────────────────┘
                                  │
                             ┌────▼─────┐
                             │  GitHub  │
                             │  (OAuth) │
                             └──────────┘

┌──────────────────────────────────────────────────────┐
│   Local Developer Machine                            │
│                                                      │
│   ┌──────────┐    MCP     ┌───────────────────────┐  │
│   │ Coding   │◄──────────►│ specmap.mcp (server)  │  │
│   │ Agent    │  (stdio)   │   ┌─────────┐         │  │
│   └──────────┘            │   │ litellm │         │  │
│                           │   │ (BYOK)  │         │  │
│                           │   └────┬────┘         │  │
│   ┌──────────┐            │        │              │  │
│   │ CI / Dev │◄───────────┤ specmap (core lib)    │  │
│   │ Terminal │  (CLI)     │   annotator, state,   │  │
│   └──────────┘            │   llm, tools, config  │  │
│                           └───────┬───────────────┘  │
│   ┌──────────┐                    │                  │
│   │ specmap  │  Typer CLI         │                  │
│   │ validate/│◄───────────────────┘                  │
│   │ status   │                                       │
│   └──────────┘            ┌───────────────┐          │
│                           │ .specmap/     │          │
│                           │ branch.json   │          │
│                           └───────────────┘          │
└──────────────────────────────────────────────────────┘
```

Both `specmap.mcp` (MCP server) and `specmap.cli` (Typer CLI) are thin entrypoints over the shared `specmap` core library in `core/src/specmap/`.

---

## Monorepo Structure

```
specmap/
├── SPEC.md
├── .gitignore
├── justfile                          # Task runner
├── core/                             # Python: core library, MCP server, CLI, API server
│   ├── pyproject.toml                # uv; deps: mcp, litellm, pydantic, unidiff, typer
│   ├── src/specmap/                  # Shared core library
│   │   ├── config.py                 # BYOK config loading (env vars, .specmap/config.json)
│   │   ├── indexer/
│   │   │   ├── code_analyzer.py      # Diff parsing, change grouping
│   │   │   ├── mapper.py             # LLM-driven annotation generation (core IP)
│   │   │   ├── diff_optimizer.py     # Hunk-level diff optimization for subsequent pushes
│   │   │   ├── spec_parser.py        # Markdown → heading hierarchy (used by tests)
│   │   │   ├── hasher.py             # Content hashing (code hash for cross-language compat)
│   │   │   └── validator.py          # Line range validation for annotations
│   │   ├── state/
│   │   │   ├── models.py             # Pydantic models: SpecmapFile v2, Annotation, SpecRef
│   │   │   └── specmap_file.py       # Read/write .specmap/{branch}.json
│   │   ├── llm/
│   │   │   ├── client.py             # litellm wrapper, retry, token counting
│   │   │   ├── prompts.py            # Annotation prompt templates
│   │   │   └── schemas.py            # Structured output schemas (AnnotationResponse)
│   │   ├── tools/
│   │   │   ├── annotate.py           # Core annotation tool
│   │   │   └── check_sync.py         # Verify annotations are valid
│   │   ├── mcp/                      # MCP server entrypoint
│   │   │   ├── __main__.py           # python -m specmap.mcp
│   │   │   └── server.py             # Tool registration
│   │   └── cli/                      # Typer CLI entrypoint
│   │       ├── __init__.py           # Typer app, global callback
│   │       ├── __main__.py           # python -m specmap.cli
│   │       ├── output.py             # Rich console helpers
│   │       └── commands/
│   │           ├── validate.py       # Line range validity check
│   │           ├── status.py         # Human-readable annotation summary
│   │           └── serve.py          # API server entrypoint
│   │       └── server/               # FastAPI server (Phase 2)
│   │           ├── config.py         # Env-based config (port, DB, OAuth, CORS)
│   │           ├── app.py            # FastAPI app factory, route registration, CORS
│   │           ├── auth.py           # OAuth, JWT, AES-256-GCM encryption
│   │           ├── github.py         # GitHub API client (repos, PRs, contents)
│   │           ├── db.py             # SQLite access (aiosqlite), migrations
│   │           ├── models.py         # Domain types
│   │           └── spa.py            # SPA static file handler with index.html fallback
│   └── tests/                        # Unit tests (pytest)
│
├── web/                              # React frontend
│   ├── vite.config.ts                # Vite + React + Tailwind, proxy /api to Python server
│   ├── index.html
│   └── src/
│       ├── api/                      # TypeScript API client
│       │   ├── types.ts              # Interfaces mirroring API models
│       │   ├── client.ts             # Fetch wrapper (credentials, 401 redirect)
│       │   └── endpoints.ts          # Typed functions for each API endpoint
│       ├── stores/                   # Zustand state management
│       │   ├── authStore.ts          # User session state
│       │   ├── reviewStore.ts        # PR + files + annotations state
│       │   └── specPanelStore.ts     # Spec side panel state
│       ├── components/
│       │   ├── layout/               # AppShell, Header
│       │   ├── diff/                 # DiffViewer, DiffFile, FileHeader, AnnotationWidget, SpecBadge
│       │   ├── spec/                 # SpecPanel, SpecContent (markdown rendering)
│       │   └── ui/                   # LoadingSpinner, ErrorBoundary, Breadcrumb
│       └── pages/                    # LoginPage, DashboardPage, RepoPage, PRReviewPage
│
├── tests/                            # Functional test suite
│   ├── conftest.py                   # Session fixtures
│   ├── harness/                      # Test infrastructure (repo, CLI runner, mocks)
│   └── scenarios/                    # End-to-end test scenarios
│
└── docs/                             # MkDocs documentation
    ├── getting-started/
    ├── cli/
    ├── mcp/
    └── concepts/
```

---

## `.specmap/` Tracking File Format

One JSON file per branch at `.specmap/{branch-name}.json`. Contains annotations with inline spec references -- natural-language descriptions of code regions with `[N]` citations pointing to spec locations.

```json
{
  "version": 2,
  "branch": "feature/add-auth",
  "base_branch": "main",
  "head_sha": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
  "updated_at": "2026-03-19T14:30:00Z",
  "updated_by": "mcp:claude-code",

  "annotations": [
    {
      "id": "ann_01HXZ...",
      "file": "api/internal/auth/session.go",
      "start_line": 15,
      "end_line": 42,
      "description": "Implements JWT session token creation and validation with httpOnly cookie storage [1] and 24-hour expiry with silent refresh [2].",
      "refs": [
        {
          "id": 1,
          "spec_file": "docs/auth-spec.md",
          "heading": "Authentication > Token Storage",
          "start_line": 45,
          "excerpt": "Sessions use signed JWTs stored in httpOnly cookies"
        },
        {
          "id": 2,
          "spec_file": "docs/auth-spec.md",
          "heading": "Authentication > Token Storage",
          "start_line": 47,
          "excerpt": "Tokens expire after 24 hours and are refreshed silently"
        }
      ],
      "created_at": "2026-03-19T14:25:00Z"
    }
  ],

  "ignore_patterns": ["*.generated.go", "*.lock", "vendor/**"]
}
```

**Key properties:**
- `head_sha` tracks the commit that was last annotated, enabling incremental diff optimization on subsequent pushes
- `description` is a natural-language summary with `[N]` inline citations referencing the `refs` list
- `refs` point to specific locations in spec files (heading + line + excerpt) for traceability
- Annotations with non-empty `refs` count as spec-covered; annotations with empty `refs` are described but not spec-linked

---

## Diff-Based Optimization

**First push:** `git diff base_branch...HEAD` produces the full diff. The LLM reads the diff along with spec files and generates annotations with `[N]` spec citations for all changed code.

**Subsequent pushes:** `git diff {previous_head_sha}..HEAD` produces an incremental diff. Existing annotations are classified:
1. **Keep** -- annotation's file/line range does not overlap with the incremental diff
2. **Shift** -- annotation's file has changes but the annotation's line range does not overlap; line numbers are mechanically adjusted based on diff hunks
3. **Regenerate** -- annotation's line range overlaps with the incremental diff; sent to LLM for fresh annotation

This makes subsequent pushes proportional to the size of the incremental change, not the total branch diff.

---

## MCP Server Tools

All tools auto-detect branch from git and auto-discover spec files by scanning for markdown in-repo.

### `specmap_annotate`
Core annotation tool. Called by agent after code changes.
- Input: optional `code_changes[]` (file paths/diffs), optional `spec_files[]`, optional `branch`, optional `context` (freeform development session context)
- Process: compute diff -> read specs -> LLM generates natural-language descriptions with [N] spec citations -> write `.specmap/{branch}.json`
- Output: annotations created/updated count

### `specmap_check`
Verify existing annotations are still valid.
- Input: optional `branch`, optional `files[]`
- Process: check that annotated line ranges still exist in the code files (no hash checks)
- Output: valid/invalid annotation counts with details

---

---

## SQLite Schema (Phase 2)

**Implemented tables** (same structure, SQLite types):
- `users` -- specmap identity (linked via `github_id`)
- `user_tokens` -- OAuth tokens, AES-256-GCM encrypted at application level
- `repositories` -- GitHub repos the user has access to
- `pull_requests` -- cached PR metadata (repo, number, title, state, branches, head SHA)
- `mapping_cache` -- server-side cache of `.specmap/` data (JSON) keyed by PR + head SHA

---

## API Design (Phase 2)

**Implemented REST endpoints (Python/FastAPI, `/api/v1`):**

| Group | Endpoints | Auth |
|-------|-----------|------|
| Health | `GET /healthz` | No |
| Auth | `GET /auth/login` (GitHub redirect), `GET /auth/callback` | No |
| Auth | `POST /auth/logout`, `GET /auth/me` | JWT |
| Repos | `GET /repos`, `GET /repos/{owner}/{repo}` | JWT |
| PRs | `GET /repos/{owner}/{repo}/pulls`, `GET .../pulls/{n}`, `GET .../pulls/{n}/files` | JWT |
| Annotations | `GET .../pulls/{n}/annotations` (fetch/cache .specmap/ from GitHub) | JWT |
| Specs | `GET .../pulls/{n}/specs/{path...}` (fetch spec content at head SHA) | JWT |

**Annotations flow:** get user token -> fetch PR from GitHub (get head_sha, head_branch) -> upsert repo+PR -> check mapping_cache -> on miss, fetch `.specmap/{head_branch}.json` via Contents API at ref=head_sha -> parse -> cache -> return. If `.specmap/` file doesn't exist (404), return empty annotations.

---

## Key Technology Choices

| Component | Choice | Why |
|-----------|--------|-----|
| Python API | `FastAPI` | Async, automatic OpenAPI docs, Pydantic integration |
| Python server | `uvicorn` | ASGI server, fast, supports auto-reload |
| Python HTTP client | `httpx` | Async HTTP client for GitHub API calls |
| Python auth | `PyJWT` + `cryptography` | JWT sessions, AES-256-GCM token encryption |
| Python DB | `aiosqlite` | Async SQLite access |
| Python CLI | `typer` (Typer >= 0.12, bundles Rich) | Click-based, auto-generates help, Rich output |
| Python MCP | `modelcontextprotocol/python-sdk` | Official SDK |
| Python LLM | `litellm` | BYOK across 100+ providers |
| Python diff | `unidiff` | Parse unified diff format |
| React diff viewer | `react-diff-view` + `gitdiff-parser` | Customizable widget injection for spec badges |
| React syntax | `prism-react-renderer` | Lightweight, works with react-diff-view |
| React state | `zustand` | Minimal boilerplate, good TS support |
| React CSS | `tailwindcss` v4 | Fast iteration for data-dense UI |
| React routing | `react-router` v7 | Standard |
| React comments | `react-markdown` | Render markdown in comments like GitHub |

---

## Security

- **OAuth**: GitHub OAuth App flow. State parameter in encrypted HttpOnly cookie. Session as short-lived JWT (1hr) in HttpOnly/Secure/SameSite=Lax cookie.
- **Token storage**: AES-256-GCM encryption at application level, key from `ENCRYPTION_KEY` env var.
- **BYOK keys**: Local only in Phase 1 (never leave user's machine). MCP server warns if API key appears in tracked files. `.specmap/config.json` added to `.gitignore` template.
- **No secrets in `.specmap/`**: Design invariant -- only annotations, references, and metadata, never API keys or credentials.

---

## Deployment

Self-hosted. Single process: `specmap serve`. SQLite database. Docker optional.

- **Single binary**: Python API server with embedded React frontend
- **Docker**: `docker build -t specmap . && docker run` with env vars
- **TLS**: handled by a reverse proxy (nginx, caddy) in front of the application
- **SQLite**: all state in a single file, WAL mode for concurrent reads, backup = copy the file

---

## Phased Delivery

### Phase 1: MCP Server + CLI (standalone, no infrastructure) -- COMPLETE
All Python. The `core/` directory contains the shared `specmap` package, the MCP server (`specmap.mcp`), and the Typer CLI (`specmap.cli`). Both entrypoints import from the same core library (`specmap.indexer`, `specmap.state`, `specmap.tools`, etc.).

A developer adds the MCP server to their coding agent, annotations are generated during development, `.specmap/` files are committed, and structural validity is checked in CI via `specmap validate`.

**Implemented files (core library):**
1. `core/src/specmap/state/models.py` -- Pydantic data models (SpecmapFile v2, Annotation, SpecRef)
2. `core/src/specmap/indexer/code_analyzer.py` -- diff parsing + change grouping
3. `core/src/specmap/indexer/mapper.py` -- LLM-driven annotation generation (core IP)
4. `core/src/specmap/indexer/diff_optimizer.py` -- hunk-level diff optimization for subsequent pushes
5. `core/src/specmap/indexer/spec_parser.py` -- markdown heading extraction
6. `core/src/specmap/indexer/hasher.py` -- content hashing for cross-language compatibility
7. `core/src/specmap/indexer/validator.py` -- line range validation
8. `core/src/specmap/state/specmap_file.py` -- read/write `.specmap/{branch}.json`
9. `core/src/specmap/llm/client.py` -- litellm wrapper
10. `core/src/specmap/llm/prompts.py` -- annotation prompt templates
11. `core/src/specmap/llm/schemas.py` -- structured output schemas (AnnotationResponse)
12. `core/src/specmap/tools/*.py` -- MCP tool implementations (annotate, check_sync)
13. `core/src/specmap/mcp/server.py` -- MCP server registration (2 tools)
14. `core/src/specmap/cli/` -- Typer CLI (validate, status commands)

### Phase 2: Web UI (read-only) + GitHub OAuth -- COMPLETE
Python FastAPI server with GitHub OAuth, JWT sessions, encrypted token storage, SQLite schema, and GitHub API integration for repos/PRs/files. React SPA with Vite + Tailwind: dashboard, repo page, PR review page with diff viewer + annotation widgets + spec side panel. Reviewer logs in with GitHub, selects a repo and PR, and sees the diff with specmap annotations inline. Clicking a `[N]` citation opens the spec content in a side panel.

**Implemented:**
- Python API: FastAPI + uvicorn, OAuth login, JWT sessions, encrypted token storage, SQLite schema, repo/PR/files endpoints, annotations endpoint (fetch/cache .specmap/ from GitHub), spec content endpoint, CORS middleware
- React: Vite scaffold, Tailwind CSS, API client layer, Zustand stores (auth, review, spec panel), router, pages (login, dashboard, repo, PR review), diff viewer (react-diff-view + gitdiff-parser), annotation widgets with [N] citation badges, spec panel with markdown rendering
- Build: justfile commands for serve, serve-dev, web-install, web-dev, web-build, web-typecheck; lint includes tsc

### Phase 3: Interactive review
Bidirectional comment sync, approvals, GitHub App webhooks, WebSocket real-time updates.

### Phase 4: Supplementation + enforcement
LLM-generated specs for unmapped code, GitHub Action for CI coverage gates, advanced sync tooling.

---

## Verification

### Phase 1 testing (COMPLETE):
- **Python unit tests**: annotation engine, diff optimizer, models, state file I/O, code analyzer (`just mcp-test`)
- **Functional tests**: end-to-end scenarios against temp git repos with deterministic LLM mocks -- exercises MCP tools, CLI commands, annotation generation (`just functional-test`)
- **Test harness**: multi-layer architecture -- conftest fixtures, GitRepo helper, LLMMockRegistry, CLIRunner (subprocess), domain assertions, reusable spec/code constants
- **CI commands**: `just test` (unit), `just test-all` (unit + functional), `just lint` (ruff)
- **Manual E2E**: Configure MCP server in Claude Code, run a coding session, verify `.specmap/` file is created correctly, run `specmap validate`

### Phase 2 testing:
- TypeScript: type checking via `npx tsc --noEmit` (`just web-typecheck`)
- Combined: `just lint` runs ruff + tsc
- CI pipeline: `just test` (Python unit), `just lint` (all linters)
