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
6. **CLI validates** -- in CI, the CLI reads the specmap file, computes coverage against the base branch, and enforces a threshold

## Component Responsibilities

| Component | Language | Responsibility | Makes LLM calls? |
|---|---|---|---|
| MCP Server | Python | Generate and maintain annotations | Yes |
| CLI | Python | Validate annotations, enforce coverage | No |
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

## Future Architecture (Phase 2+)

```mermaid
graph TB
    subgraph "Developer Workstation"
        Agent[Coding Agent]
        MCP[MCP Server]
    end

    subgraph "Specmap Cloud"
        Web[React SPA]
        API[Go API]
        DB[(PostgreSQL)]
    end

    subgraph "GitHub"
        GHA[GitHub Action]
        PR[Pull Requests]
    end

    Agent -->|MCP stdio| MCP
    MCP -->|API calls| API
    Web -->|REST| API
    API -->|read/write| DB
    GHA -->|API calls| API
    GHA -->|comments| PR
    API -->|webhooks| PR
```

Phase 2 adds a web UI, Go API server, and PostgreSQL for multi-user collaboration. Phase 3 adds interactive review and comment sync. Phase 4 adds a dedicated GitHub Action. See [Roadmap](../roadmap.md) for details.
