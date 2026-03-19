# Specmap Implementation Plan

## Context

AI coding agents generate large volumes of code, but humans still need to review it. Development is increasingly spec-driven — agents write plans/specs, then generate code from them. Specmap bridges this gap by mapping spec text (intent) to code changes, so reviewers can see *why* code exists alongside *what* it does. Reviewers answer two questions: Is this intent what we want? Does the code match the intent?

This is a greenfield project targeting startup viability. Phase 1 (MCP server + CLI) is standalone and immediately useful without any server infrastructure.

---

## Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   React SPA     │    │   Go API Server  │    │   PostgreSQL     │
│   (Vite)        │◄──►│   (net/http)     │◄──►│   (RDS)          │
│   S3+CloudFront │    │   ECS Fargate    │    │                  │
└─────────────────┘    └──────┬───────────┘    └──────────────────┘
                              │  ▲
                    WebSocket │  │ Webhooks
                              │  │
                         ┌────▼──┴───┐
                         │  GitHub   │
                         │  (App+    │
                         │   OAuth)  │
                         └───────────┘

┌─────────────────────────────────────────────┐
│   Local Developer Machine                    │
│                                              │
│   ┌──────────┐    MCP     ┌──────────────┐  │
│   │ Coding   │◄──────────►│ Python MCP   │  │
│   │ Agent    │  (stdio)   │ Server       │  │
│   └──────────┘            │  ┌─────────┐ │  │
│                           │  │ litellm │ │  │
│                           │  │ (BYOK)  │ │  │
│                           │  └────┬────┘ │  │
│                           └───────┼──────┘  │
│                                   │         │
│                           ┌───────▼──────┐  │
│                           │ .specmap/    │  │
│                           │ branch.json  │  │
│                           └──────────────┘  │
└─────────────────────────────────────────────┘
```

---

## Monorepo Structure

```
specmap/
├── SPEC.md
├── .gitignore
├── justfile                          # Task runner
├── docker-compose.yml                # Local dev (Postgres, etc.)
│
├── mcp/                              # Python MCP server + LLM orchestration
│   ├── pyproject.toml                # uv; deps: mcp, litellm, pydantic, mistune, unidiff
│   ├── src/specmap_mcp/
│   │   ├── __main__.py               # Entry: starts MCP server on stdio
│   │   ├── server.py                 # Tool registration
│   │   ├── config.py                 # BYOK config loading (env vars, .specmap/config.json)
│   │   ├── tools/
│   │   │   ├── map_code_to_spec.py   # Core mapping tool
│   │   │   ├── check_sync.py         # Verify mappings current
│   │   │   ├── get_unmapped.py       # Find uncovered code
│   │   │   └── reindex.py            # Selective re-indexing
│   │   ├── indexer/
│   │   │   ├── spec_parser.py        # Markdown → heading hierarchy + hashes
│   │   │   ├── code_analyzer.py      # Diff parsing, change grouping
│   │   │   ├── mapper.py             # LLM-driven semantic mapping (core IP)
│   │   │   └── hasher.py             # Hierarchical hashing functions
│   │   ├── state/
│   │   │   ├── models.py             # Pydantic models for .specmap/ format
│   │   │   ├── specmap_file.py       # Read/write .specmap/{branch}.json
│   │   │   └── relocator.py          # Stale span relocation (fuzzy match)
│   │   └── llm/
│   │       ├── client.py             # litellm wrapper, retry, token counting
│   │       ├── prompts.py            # Mapping/reindex prompt templates
│   │       └── schemas.py            # Structured output schemas
│   └── tests/
│
├── cli/                              # Go CLI for validation + CI
│   ├── go.mod
│   ├── main.go
│   ├── cmd/
│   │   ├── root.go                   # Global flags (--repo-root, --branch, --no-color)
│   │   ├── validate.go               # Schema + hash integrity check
│   │   ├── status.go                 # Human-readable mapping summary
│   │   └── check.go                  # CI mode: --threshold, --base, --json
│   └── internal/
│       ├── specmap/
│       │   ├── reader.go             # Parse .specmap/ JSON
│       │   ├── validator.go          # Hash verification
│       │   └── coverage.go           # Coverage calculation
│       └── git/
│           └── diff.go               # git diff integration
│
├── api/                              # Go API server (Phase 2+)
│   ├── go.mod
│   ├── cmd/api/main.go
│   └── internal/
│       ├── config/                   # Env-based config
│       ├── server/                   # HTTP setup, middleware, routes
│       ├── auth/                     # OAuth flow, JWT sessions
│       ├── github/                   # GitHub API client, webhooks, App management
│       ├── handlers/                 # auth, pulls, specs, comments, coverage, ws
│       ├── models/                   # User, Team, Installation, PR, Comment, Mapping
│       ├── store/                    # Postgres access layer + migrations
│       ├── ws/                       # WebSocket hub, rooms, typed messages
│       └── sync/                     # Bidirectional comment sync, mapping cache refresh
│
├── web/                              # React frontend (Phase 2+)
│   ├── vite.config.ts
│   └── src/
│       ├── api/                      # Typed fetch wrappers
│       ├── hooks/                    # useWebSocket, useAuth, usePullRequest, useSpecMappings
│       ├── components/
│       │   ├── diff/                 # DiffViewer, DiffFile, DiffLine, DiffGutter
│       │   ├── spec/                 # SpecPanel, SpecBadge, CoverageBar
│       │   ├── comments/             # CommentThread, CommentForm, CommentList
│       │   └── pr/                   # PRList, PRDetail, PRHeader
│       ├── pages/                    # Login, Dashboard, PRReview, Settings
│       └── stores/                   # Zustand (authStore, reviewStore)
│
├── action/                           # GitHub Action (Phase 4)
│
├── infra/                            # Terraform
│   ├── modules/
│   │   ├── networking/               # VPC, subnets, security groups
│   │   ├── ecs/                      # Fargate task defs + service
│   │   ├── lambda/                   # Python LLM service
│   │   ├── rds/                      # PostgreSQL
│   │   ├── cdn/                      # S3 + CloudFront
│   │   └── secrets/                  # AWS Secrets Manager
│   └── environments/
│       ├── dev/
│       └── prod/
│
└── docs/
    ├── architecture.md
    ├── api.md
    ├── mcp-tools.md
    └── specmap-format.md
```

---

## `.specmap/` Tracking File Format

One JSON file per branch at `.specmap/{branch-name}.json`. Contains only pointers and hashes — no text content.

```json
{
  "version": 1,
  "branch": "feature/add-auth",
  "base_branch": "main",
  "updated_at": "2026-03-19T14:30:00Z",
  "updated_by": "mcp:claude-code",

  "spec_documents": {
    "docs/auth-spec.md": {
      "doc_hash": "sha256:a1b2c3d4e5f6...",
      "sections": {
        "Authentication > Token Storage": {
          "heading_path": ["Authentication", "Token Storage"],
          "heading_line": 45,
          "section_hash": "sha256:789abc..."
        }
      }
    }
  },

  "mappings": [
    {
      "id": "m_01HXZ...",
      "spec_spans": [
        {
          "spec_file": "docs/auth-spec.md",
          "heading_path": ["Authentication", "Token Storage"],
          "span_offset": 120,
          "span_length": 245,
          "span_hash": "sha256:def012...",
          "relevance": 1.0
        }
      ],
      "code_target": {
        "file": "api/internal/auth/session.go",
        "start_line": 15,
        "end_line": 42,
        "content_hash": "sha256:9ab0cd..."
      },
      "stale": false,
      "created_at": "2026-03-19T14:25:00Z"
    }
  ],

  "ignore_patterns": ["*.generated.go", "*.lock", "vendor/**"]
}
```

**Key properties:**
- `spec_spans` sorted by `relevance` descending (primary intent first)
- `heading_path` is the semi-stable anchor for span relocation
- `content_hash` on code side detects drift independently of line numbers
- `stale` flag set when relocation fails — UI surfaces these prominently

---

## Hierarchical Hashing & Re-indexing

**Hash levels (all SHA-256, truncated to 16 hex chars):**
1. **Document hash** — hash of entire spec file content
2. **Section hash** — hash of content under a heading (to next heading of same/higher level)
3. **Span hash** — hash of the specific span text at offset+length
4. **Code hash** — hash of the code region content

**Re-indexing flow (proportional to change, not document size):**
1. Compare document-level hash → unchanged docs skipped entirely
2. Walk sections of changed docs → compare section hashes → unchanged sections skipped
3. For changed sections, check span hashes → unchanged spans keep mappings
4. Broken spans (hash mismatch): relocate within same section using heading anchor + fuzzy match
5. If relocation fails: mark `stale: true`
6. Only stale/broken mappings sent to LLM for re-indexing

For code-side changes, `git diff` provides the deltas directly.

---

## MCP Server Tools

All tools auto-detect branch from git and auto-discover spec files by scanning for markdown in-repo.

### `map_code_to_spec`
Core indexing tool. Called by agent after code changes.
- Input: optional `code_changes[]` (file paths/diffs), optional `spec_files[]`, optional `branch`
- Process: compute diffs → parse specs → call LLM to identify semantic mappings → write `.specmap/{branch}.json`
- Output: mappings created/updated count, coverage delta

### `check_sync`
Verify existing mappings are still valid.
- Input: optional `branch`, optional `files[]`
- Process: re-compute hashes for each mapping's spec span + code target → attempt relocation for mismatches
- Output: valid/relocated/stale mapping counts with details

### `get_unmapped_changes`
Find code without spec coverage.
- Input: optional `branch`, optional `base_branch`, optional `threshold`
- Output: unmapped file/line ranges, overall + per-file coverage percentages

### `reindex`
Targeted re-indexing proportional to change size.
- Input: optional `spec_files[]`, optional `code_files[]`, optional `force` boolean
- Process: hierarchical hash comparison → only re-index changed sections/files
- Output: updated mappings

---

## Spec Coverage (First-Class Concept)

**Metric:** mapped changed lines / total changed lines (against base branch)

**Surfaces in:**
- MCP server: `get_unmapped_changes` reports coverage
- CLI: `specmap check --threshold 0.80` for CI enforcement (exit 1 if below)
- UI: CoverageBar component per-file and per-PR
- GitHub Action (Phase 4): quality gate with configurable threshold

**CLI output example:**
```
specmap: checking coverage for feature/add-auth (base: main)
Files: 10/12 mapped | Lines: 245/298 mapped
Unmapped: auth/middleware.go (0%, 38 lines), hooks/useAuth.ts (0%, 15 lines)
Stale: auth/session.go:15-42 (spec span hash mismatch)
Overall: 82.2% (threshold: 80.0%) — PASS
```

---

## PostgreSQL Schema (Phase 2+)

**Core tables:**
- `users` — specmap identity (linked via `github_id`)
- `user_tokens` — OAuth tokens, AES-256-GCM encrypted at application level
- `teams` — specmap's own org concept
- `team_members` — role-based (owner/admin/member)
- `installations` — GitHub App installations, linked to teams
- `repositories` — repos via installations
- `pull_requests` — cached PR metadata + `spec_coverage` (float)
- `comments` — with `sync_status` (pending/synced/failed/conflict), `sync_direction`
- `webhook_events` — raw payload log for debugging/replay
- `mapping_cache` — server-side cache of `.specmap/` data keyed by PR + head_sha

---

## API Design (Phase 2+)

**REST endpoints (Go, `/api/v1`):**

| Group | Endpoints |
|-------|-----------|
| Auth | `GET /auth/login` → GitHub redirect, `GET /auth/callback`, `POST /auth/logout`, `GET /auth/me` |
| Repos | `GET /repos`, `GET /repos/{owner}/{repo}` |
| PRs | `GET /repos/{owner}/{repo}/pulls`, `GET .../pulls/{n}`, `GET .../pulls/{n}/diff`, `GET .../pulls/{n}/mappings`, `GET .../pulls/{n}/coverage` |
| Comments | `GET/POST/PATCH/DELETE .../pulls/{n}/comments[/{id}]` |
| Specs | `GET .../pulls/{n}/specs`, `GET .../pulls/{n}/specs/{path}` (fetches content at head_sha) |
| Teams | `GET/POST /teams`, `GET /teams/{slug}`, `POST/DELETE .../members` |
| Webhooks | `POST /webhooks/github` (signature-verified, no auth) |

**WebSocket protocol (`GET /api/v1/ws?token={jwt}`):**
- Client subscribes: `{"type": "subscribe", "channel": "pr:owner/repo:42"}`
- Server pushes: `comment.created`, `comment.updated`, `comment.deleted`, `mappings.updated`, `pr.force_pushed`
- Keepalive: `ping`/`pong`

---

## Key Technology Choices

| Component | Choice | Why |
|-----------|--------|-----|
| Go HTTP | `net/http` (1.22+) | User preference; 1.22 pattern routing eliminates need for external router |
| Go WebSocket | `nhooyr.io/websocket` | Modern, context-aware, lighter than gorilla |
| Go DB driver | `jackc/pgx/v5` | High-performance Postgres, native types, pooling |
| Go migrations | `golang-migrate/migrate` + embedded SQL | Simple, file-based |
| Go GitHub client | `google/go-github/v60` | Well-maintained, typed |
| Go CLI | `spf13/cobra` | Standard, subcommand support |
| Python MCP | `modelcontextprotocol/python-sdk` | Official SDK |
| Python LLM | `litellm` | BYOK across 100+ providers |
| Python markdown | `mistune` | AST-based parsing for section extraction |
| Python diff | `unidiff` | Parse unified diff format |
| React diff viewer | `react-diff-view` + `gitdiff-parser` | Customizable widget injection for spec badges |
| React syntax | `prism-react-renderer` | Lightweight, works with react-diff-view |
| React state | `zustand` | Minimal boilerplate, good TS support |
| React CSS | `tailwindcss` v4 | Fast iteration for data-dense UI |
| React routing | `react-router` v7 | Standard |
| React comments | `react-markdown` | Render markdown in comments like GitHub |

---

## Security

- **OAuth**: GitHub App-based OAuth flow. State parameter in encrypted HttpOnly cookie. Session as short-lived JWT (1hr) in HttpOnly/Secure/SameSite=Lax cookie.
- **Token storage**: AES-256-GCM encryption at application level, key from AWS Secrets Manager.
- **BYOK keys**: Local only in Phase 1 (never leave user's machine). MCP server warns if API key appears in tracked files. `.specmap/config.json` added to `.gitignore` template.
- **Webhook verification**: HMAC-SHA256 signature check on every webhook. Reject + log failures.
- **Permission intersection**: User must have both specmap team membership AND GitHub repo access. GitHub access verified via user's OAuth token, cached 5min.
- **Echo loop prevention**: Comment sync skips comments authored by the GitHub App bot.
- **Rate limiting**: Per-user token bucket on API endpoints.
- **No secrets in `.specmap/`**: Design invariant — only hashes and pointers, never text content.

---

## Deployment (AWS + Terraform)

**Demo (~$25-35/mo):**
- Frontend: S3 + CloudFront (pennies)
- Go API: ECS Fargate, 1 task (0.25 vCPU, 0.5GB RAM) ~$9/mo
- Python LLM: Lambda (pay-per-invocation) — near-zero at demo scale
- Postgres: RDS `db.t4g.micro` ~$13/mo
- WebSockets: Within Go Fargate task

**Scale path:**
- Fargate: add tasks horizontally
- Lambda → Fargate if cold starts matter
- RDS → Aurora Serverless v2
- Add ElastiCache/Redis for rate limiting + caching

---

## Phased Delivery

### Phase 1: MCP Server + CLI (standalone, no infrastructure)
Build the Python MCP server with all 4 tools and the Go CLI with validate/status/check commands. A developer adds the MCP server to their coding agent, mappings are generated during development, `.specmap/` files are committed, and coverage is checked in CI.

**Key files to implement first:**
1. `mcp/src/specmap_mcp/state/models.py` — data contract shared across all components
2. `mcp/src/specmap_mcp/indexer/hasher.py` — hierarchical hashing foundation
3. `mcp/src/specmap_mcp/indexer/spec_parser.py` — markdown → section hierarchy
4. `mcp/src/specmap_mcp/indexer/code_analyzer.py` — diff parsing + change grouping
5. `mcp/src/specmap_mcp/indexer/mapper.py` — LLM-driven mapping (core IP)
6. `mcp/src/specmap_mcp/state/specmap_file.py` — read/write `.specmap/{branch}.json`
7. `mcp/src/specmap_mcp/state/relocator.py` — stale span relocation
8. `mcp/src/specmap_mcp/llm/client.py` — litellm wrapper
9. `mcp/src/specmap_mcp/llm/prompts.py` — mapping prompt templates
10. `mcp/src/specmap_mcp/tools/*.py` — all 4 tool implementations
11. `mcp/src/specmap_mcp/server.py` — MCP server registration
12. `cli/` — Go CLI (reader, validator, coverage, commands)

### Phase 2: Web UI (read-only) + GitHub OAuth
Go API server, React diff viewer with spec panel, GitHub OAuth login. Reviewers can see diffs with spec annotations and coverage.

### Phase 3: Interactive review
Bidirectional comment sync, approvals, GitHub App webhooks, WebSocket real-time updates.

### Phase 4: Supplementation + enforcement
LLM-generated specs for unmapped code, GitHub Action for CI coverage gates, advanced sync tooling.

---

## Verification

### Phase 1 testing:
- **Python unit tests**: spec parser, hasher, code analyzer, relocator, models (no LLM needed)
- **Python integration tests**: full tool flows against temp git repos; LLM calls mocked via `unittest.mock.patch` on `litellm.acompletion` (or recorded cassettes via vcrpy)
- **Go unit tests**: reader, validator, coverage with known fixtures
- **Go integration tests**: CLI invoked against temp git repos with sample `.specmap/` files
- **Manual E2E**: Configure MCP server in Claude Code, run a coding session, verify `.specmap/` file is created correctly, run `specmap check`

### Phase 2+ testing:
- Go API: handler tests with `httptest`, store tests with `testcontainers-go` (Postgres)
- React: component tests with Vitest + Testing Library
- E2E: Playwright for login → view PR → post comment flow (Phase 3)
- CI pipeline: `uv run pytest --cov`, `go test ./...`, `go vet`, linters
