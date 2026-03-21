# Architecture

## System Diagram

```mermaid
graph TB
    subgraph "Developer Workstation"
        Agent[Coding Agent<br/>e.g. Claude Code]
        MCP[Specmap MCP Server<br/>Python]
        SF[".specmap/{branch}.json"]
        CLI[Specmap CLI<br/>Python]
        Specs[Spec Documents<br/>*.md]
        Code[Source Code]
    end

    subgraph "External"
        LLM[LLM Provider<br/>OpenAI / Anthropic / etc.]
    end

    subgraph "CI"
        GH[GitHub Actions]
    end

    Agent -->|MCP stdio| MCP
    MCP -->|reads| Specs
    MCP -->|reads| Code
    MCP -->|LLM calls| LLM
    MCP -->|reads/writes| SF
    CLI -->|reads| SF
    CLI -->|git diff| Code
    GH -->|runs| CLI
```

## Data Flow

1. **Agent changes code** -- the coding agent creates or modifies source files
2. **MCP tool call** -- the agent calls `specmap_annotate` via the MCP stdio protocol
3. **Diff analysis** -- the MCP server runs `git diff` to find changes (full diff on first push, incremental diff on subsequent pushes)
4. **LLM annotation** -- the server sends the diff and spec files to the LLM, which generates natural-language descriptions with `[N]` spec citations
5. **Persist** -- annotations are written to `.specmap/{branch}.json` with the current `head_sha`
6. **CLI validates** -- in CI, the CLI reads the specmap file and validates annotation line ranges

## Component Responsibilities

| Component | Language | Responsibility | Makes LLM calls? |
|---|---|---|---|
| MCP Server | Python | Generate and maintain annotations | Yes |
| CLI | Python | Validate annotations | No |
| `.specmap/` files | JSON | Store annotations with spec references | -- |
| Spec documents | Markdown | Source of truth for requirements | -- |

## Design Principles

**Annotations with spec citations**
: The specmap file stores natural-language descriptions of code regions with inline `[N]` references to spec locations. Spec excerpts provide context, but the spec documents remain the source of truth.

**BYOK (Bring Your Own Key)**
: The MCP server never bundles API keys or requires a specific provider. Users configure their preferred LLM via environment variables.

**Local-first (Phase 1)**
: No server, no database, no accounts. Everything runs on the developer's machine. The specmap file is committed to git alongside the code.

**Deterministic CLI**
: The CLI makes no network calls and no LLM calls. Its output is fully deterministic given the same inputs, making it reliable for CI.

## Phase 2 Architecture (In Progress)

```mermaid
graph TB
    subgraph "Developer Workstation"
        Agent[Coding Agent]
        MCP[MCP Server]
        Vite[Vite Dev Server<br/>:5173]
    end

    subgraph "Specmap Server"
        Web[React SPA]
        API[Go API<br/>:8080]
        DB[(PostgreSQL)]
    end

    subgraph "GitHub"
        OAuth[GitHub OAuth]
        Contents[Contents API]
        PR[Pull Requests]
    end

    Agent -->|MCP stdio| MCP
    Vite -->|proxy /api| API
    Web -->|REST| API
    API -->|read/write| DB
    API -->|OAuth token exchange| OAuth
    API -->|fetch .specmap/ + specs| Contents
```

Phase 2 adds a read-only web UI for reviewing PRs with spec annotations. Reviewers log in with GitHub, browse repos and PRs, and see diffs with annotation widgets inline. Clicking a `[N]` citation opens the spec content in a side panel.

The Go API server fetches `.specmap/{branch}.json` from the repo via the GitHub Contents API and caches the result in PostgreSQL. Spec file content is fetched on demand when a reviewer opens a citation.

See [Roadmap](../roadmap.md) for the full phased delivery plan.
