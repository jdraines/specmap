# Installation

## Prerequisites

- **Python 3.11+** — for the MCP server
- **Go 1.22+** — for the CLI
- **git** — for diff analysis and branch detection
- **uv** — recommended Python package manager ([install](https://docs.astral.sh/uv/getting-started/installation/))
- An **MCP-capable coding agent** (e.g., Claude Code)

## Install the MCP Server

```bash
cd mcp
uv sync
```

This installs all dependencies into a managed virtual environment.

## Build the CLI

```bash
cd cli
go build -o specmap .
```

Optionally, move the binary to your `$PATH`:

```bash
sudo mv cli/specmap /usr/local/bin/
```

## Using just

If you have [just](https://github.com/casey/just) installed, the project provides shortcuts:

```bash
just mcp-install   # Install MCP server dependencies
just cli-build     # Build CLI binary
```

## Add the MCP Server to Your Coding Agent

### Claude Code

Create or edit `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "specmap": {
      "command": "uv",
      "args": ["run", "--directory", "./mcp", "python", "-m", "specmap_mcp"],
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
uv run --directory ./mcp python -m specmap_mcp
```

## Verify Installation

Run the MCP server tests and CLI tests to confirm everything works:

```bash
just mcp-test
just cli-test
```
