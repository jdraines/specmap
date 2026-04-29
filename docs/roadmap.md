# Roadmap

Specmap is delivered in phases, each building on the previous.

## Phase 1 -- MCP Server + CLI :material-check-circle:{ .green }

**Status: Implemented**

The foundation: a local-only workflow with no infrastructure dependencies.

- **MCP server** (Python) -- 2 tools for annotating code and checking validity
- **CLI** (Python) -- `annotate`, `validate`, `status`, `config`, and `hook` commands
- **Specmap format v2** -- `.specmap/{branch}.json` with annotations, spec references, and `head_sha` for incremental optimization
- **BYOK** -- any LLM provider via litellm
- **Diff-based optimization** -- first push annotates all changes; subsequent pushes use incremental diffs to keep/shift/regenerate annotations

## Phase 2 -- Web UI + AI Review :material-check-circle:{ .green }

**Status: Implemented**

A full web interface for reviewing PRs with spec annotations and AI-powered analysis.

- **React SPA** -- browse repos, PRs, and diffs with annotation widgets inline; click `[N]` citations to open spec content in a side panel
- **Python API server (FastAPI)** -- REST API backed by SQLite; PAT or OAuth authentication; JWT sessions
- **Forge auto-detection** -- supports GitHub and GitLab, auto-detected from `git remote origin`
- **Annotation generation from web UI** -- lite mode (forge API, no clone) and full mode (local clone) with streaming progress and resume support
- **Guided walkthroughs** -- AI-generated narrative tours through PRs, configurable by familiarity level and depth, with per-step chat
- **AI code review** -- three-phase review pipeline (file-level review, cross-boundary check, consolidation) with severity ratings (P0-P4), suggested fixes, and per-issue chat
- **Chat agent** -- Pydantic AI agent with codebase tools (search, grep, read files) for investigating code and answering questions
- **PR comments** -- fetch and display GitHub/GitLab PR comment threads inline in diffs
- **Keyboard navigation** -- `j`/`k` for files, `n`/`p` for annotations, `?` for help overlay

## Phase 3 -- Deeper Integration

**Status: Partially implemented**

Tighter integration with the code review workflow.

- [x] **PR review view** -- spec annotations inline with PR diffs
- [x] **Comment display** -- PR comments from GitHub/GitLab shown inline
- [ ] **Webhook integration** -- auto-update annotations on push events
- [ ] **Review assignments** -- assign spec sections to reviewers
- [ ] **Stale notifications** -- alert when annotations need regeneration

## Phase 4 -- Supplementation + GitHub Action

**Status: Planned**

Automated spec generation and turnkey CI.

- **LLM-generated specs** -- auto-draft spec text for unmapped code
- **`specmap-action`** -- dedicated GitHub Action for one-line CI setup
- **PR comments** -- post coverage summaries as PR comments automatically
- **Spec suggestions** -- suggest spec improvements based on code changes
