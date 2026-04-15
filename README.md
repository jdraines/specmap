# Specmap

**Map AI-generated code changes back to spec intent.**

Specmap generates LLM-powered annotations that link code changes to specification documents. When an AI agent writes code, reviewers can see *which spec requirements* each code region implements, with inline `[N]` citations pointing to the exact spec sections.

## How It Works

1. **MCP server** integrates with your coding agent (e.g., Claude Code) to annotate code changes with spec references as you work
2. **CLI** validates annotations in CI (`specmap validate`)
3. **Web UI** lets reviewers browse PRs with spec annotations overlaid on diffs

```
Coding Agent ──MCP──► Specmap Server ──LLM──► .specmap/{branch}.json
                          │                          │
                     reads specs                committed to git
                     reads diffs                     │
                                                     ▼
                                              specmap validate (CI)
                                              specmap serve (Web UI)
```

## Use Specmap on Your Projects

No need to clone this repo. Install as a tool and use it in any project:

```bash
# Install
uv tool install git+https://github.com/jdraines/specmap.git#subdirectory=core

# Verify
specmap --version
```

Add the MCP server to your coding agent (`.mcp.json` in your project):

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

See the [full documentation](https://specmap.dev) for configuration, CLI commands, and CI integration.

## Develop Specmap

Clone and run locally:

```bash
git clone https://github.com/jdraines/specmap.git
cd specmap

# Install dependencies
just mcp-install     # Python (core library, MCP server, CLI, API server)
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
├── core/          Python: core library, MCP server, CLI, API server
├── web/           React frontend (Vite + Tailwind)
├── tests/         Functional test suite
├── docs/          MkDocs documentation
└── justfile       Task runner (run `just` to see all commands)
```

## License

See [LICENSE](LICENSE).
