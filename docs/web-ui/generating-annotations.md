# Generating Annotations

Annotations can be generated directly from the web UI, in addition to the [CLI](../cli/commands.md#annotate) and [MCP server](../mcp/tools.md#specmap_annotate). Open a PR in the web UI and click **Generate Annotations** in the toolbar.

## Generation Modes

| Mode | How it works | When to use |
|------|-------------|-------------|
| **Lite** | Fetches file content and patches via the forge API (GitHub/GitLab). No local clone needed. | Default mode. Works for any PR you can access. |
| **Full** | Clones the repository locally, then runs the annotation engine with full file context. | When lite mode produces incomplete results (e.g., very large PRs or complex cross-file changes). |

Both modes stream progress to the UI in real-time via server-sent events (SSE).

## Progress Tracking

During generation, the UI shows:

1. **Starting** -- initializing the generation pipeline
2. **Fetching context** -- loading spec files and PR diffs (lite mode) or cloning the repo (full mode)
3. **Annotating** -- processing files in batches. Shows `batch N/total` progress
4. **Complete** -- annotations are ready and displayed inline in the diff

## Options

| Option | Description |
|--------|-------------|
| Force regenerate | Discard existing annotations and regenerate from scratch |
| Timeout | Maximum time for generation (default: from config) |
| Concurrency | Number of parallel file batches (default: 1) |

## Resume Support

If generation is interrupted (browser closed, network issue), the server retains partial results. Reopening the PR and clicking Generate again picks up where it left off rather than starting from scratch.

## How It Compares

| Feature | Web UI | CLI (`specmap annotate`) | MCP (`specmap_annotate`) |
|---------|--------|--------------------------|--------------------------|
| Trigger | Click in browser | Run in terminal | Coding agent calls tool |
| Auth | Forge token (PAT/OAuth) | Local git repo | Local git repo |
| Incremental | Yes (resume) | Yes (diff-based) | Yes (diff-based) |
| Progress | Real-time streaming | Terminal output | Tool response |
| Persistence | `.specmap/{branch}.json` (local repo) or server-side | `.specmap/{branch}.json` | `.specmap/{branch}.json` |

All three methods produce the same annotation format and can read each other's output. Annotations generated in the web UI are saved to the local `.specmap/` directory if the server is running inside the target repository.
