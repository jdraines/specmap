# Specmap

**Map AI-generated code changes back to spec intent.**

Specmap generates LLM-powered annotations that link code changes to specification documents. When an AI agent writes code, reviewers can see *which spec requirements* each code region implements, with inline `[N]` citations pointing to the exact spec sections.

## Quick Start

```bash
pip install specmap
specmap serve
```

The web UI opens in your browser. Browse PRs, generate spec-linked annotations, run AI walkthroughs, and get code reviews -- all from one interface.

## How It Works

1. **Web UI** (`specmap serve`) -- browse PRs with spec annotations overlaid on diffs. Generate AI walkthroughs that narrate the changes step by step, run code reviews with severity ratings and suggested fixes, and chat with an AI assistant about the code.
2. **MCP server** integrates with your coding agent (e.g., Claude Code) to annotate code changes automatically as you work
3. **CLI** generates annotations (`specmap annotate`), validates them in CI (`specmap validate`), and manages configuration

```
specmap serve
    │
    ├── Browse PRs with inline spec annotations
    ├── Generate annotations (lite or full mode)
    ├── AI walkthroughs (guided narrative of changes)
    ├── AI code review (P0-P4 severity, suggested fixes)
    └── Chat (investigate code with codebase tools)

Coding Agent ──MCP──► Specmap Server ──LLM──► .specmap/{branch}.json
                          │                          │
                     reads specs                committed to git
                     reads diffs                     │
                                                     ▼
                                              specmap validate (CI)
```

## Use Specmap on Your Projects

No need to clone this repo. Install as a tool and use it in any project:

```bash
# Install from PyPI
pip install specmap

# Or via uv
uv tool install specmap

# Verify
specmap --version
```

Launch the web UI to review PRs with annotations, walkthroughs, and code reviews:

```bash
specmap serve
```

Or add the MCP server to your coding agent (`.mcp.json` in your project):

```json
{
  "mcpServers": {
    "specmap": {
      "command": "specmap-mcp",
      "env": {
        "SPECMAP_API_KEY": "sk-..."
      }
    }
  }
}
```

See the [full documentation](https://specmap.dev) for configuration, CLI commands, and deployment.

## Features

- **Spec annotations** -- LLM-generated descriptions of code regions with `[N]` citations to spec documents
- **Guided walkthroughs** -- AI-narrated tours of PRs, configurable by familiarity level and depth
- **AI code review** -- three-phase review pipeline with P0-P4 severity ratings, suggested fixes, and per-issue chat
- **Chat agent** -- ask questions about code with tools for searching annotations, grepping the codebase, and reading files
- **Diff-based optimization** -- incremental annotation updates proportional to the change size
- **BYOK** -- bring your own key; any LLM provider via litellm (OpenAI, Anthropic, Azure, Ollama, etc.)
- **GitHub + GitLab** -- auto-detected forge provider with PAT or OAuth authentication

## Develop Specmap

Clone and run locally:

```bash
git clone https://github.com/jdraines/specmap.git
cd specmap

# Install dependencies
just install         # Python (core library, MCP server, CLI, API server)
just web-install     # Node (React frontend)

# Run full dev stack (API + Vite dev server)
just dev

# Run tests
just test-all        # Unit + functional tests
just lint            # ruff + tsc

# Build wheel with bundled frontend
just build
```

To run the web UI locally, you'll need a forge token (PAT or OAuth). See [Development](docs/development.md) for the complete setup.

### Prerequisites

| Tool | Install |
|------|---------|
| Python 3.11+ | System package manager |
| [uv](https://docs.astral.sh/uv/) | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js 20+ | System package manager |
| [just](https://github.com/casey/just) | `cargo install just` or [system packages](https://github.com/casey/just#installation) |
| git | System package manager |

## Project Structure

```
specmap/
├── src/specmap/   Python: core library, MCP server, CLI, API server
├── web/           React frontend (Vite + Tailwind)
├── tests/         Test suite (unit + functional)
├── docs/          MkDocs documentation
└── justfile       Task runner (run `just` to see all commands)
```

## License

See [LICENSE](LICENSE).
