# Roadmap

Specmap is delivered in four phases, each building on the previous.

## Phase 1 -- MCP Server + CLI :material-check-circle:{ .green }

**Status: Implemented**

The foundation: a local-only workflow with no infrastructure dependencies.

- **MCP server** (Python) -- 3 tools for annotating code, checking validity, and finding coverage gaps
- **CLI** (Python) -- `validate`, `status`, `check` commands for CI enforcement
- **Specmap format v2** -- `.specmap/{branch}.json` with annotations, spec references, and `head_sha` for incremental optimization
- **BYOK** -- any LLM provider via litellm
- **Diff-based optimization** -- first push annotates all changes; subsequent pushes use incremental diffs to keep/shift/regenerate annotations

## Phase 2 -- Web UI + GitHub OAuth

**Status: Planned**

Multi-user collaboration with a web interface.

- **React SPA** -- browse specs, annotations, and coverage visually
- **Go API server** -- REST API backed by PostgreSQL
- **GitHub OAuth** -- authenticate with GitHub, auto-discover repos
- **Annotation storage** -- transition from local JSON to server-side storage
- **Spec browser** -- navigate spec documents with inline coverage indicators

## Phase 3 -- Interactive Review + Comment Sync

**Status: Planned**

Tighter integration with the code review workflow.

- **PR review view** -- see spec annotations inline with PR diffs
- **Comment sync** -- link GitHub PR comments to spec sections
- **Webhook integration** -- auto-update annotations on push events
- **Review assignments** -- assign spec sections to reviewers
- **Stale notifications** -- alert when annotations need regeneration

## Phase 4 -- Supplementation + GitHub Action

**Status: Planned**

Automated spec generation and turnkey CI.

- **LLM-generated specs** -- auto-draft spec text for unmapped code
- **`specmap-action`** -- dedicated GitHub Action for one-line CI setup
- **PR comments** -- post coverage summaries as PR comments automatically
- **Spec suggestions** -- suggest spec improvements based on code changes
