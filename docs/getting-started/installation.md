# Installation

## Prerequisites

- **Python 3.11+** — for the MCP server and CLI
- **git** — for diff analysis and branch detection
- **uv** — recommended Python package manager ([install](https://docs.astral.sh/uv/getting-started/installation/))
- An **MCP-capable coding agent** (e.g., Claude Code)

## Install

```bash
cd core
uv sync
```

This installs all dependencies (core library, MCP server, CLI) into a managed virtual environment.

## Using just

If you have [just](https://github.com/casey/just) installed, the project provides shortcuts:

```bash
just mcp-install   # Install all Python dependencies
just cli-run       # Run the CLI
```

## Add the MCP Server to Your Coding Agent

### Claude Code

Create or edit `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "specmap": {
      "command": "uv",
      "args": ["run", "--directory", "./core", "python", "-m", "specmap.mcp"],
      "env": {
        "SPECMAP_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

!!! warning "Keep your API key safe"
    Don't commit `.mcp.json` with real API keys. Use environment variables or add it to `.gitignore`.

### Other MCP Clients

Specmap uses the standard MCP stdio transport. Any client that supports stdio-based MCP servers can connect using:

```bash
uv run --directory ./core python -m specmap.mcp
```

## Verify Installation

Run the tests to confirm everything works:

```bash
just mcp-test
```
