# Installation

## Prerequisites

- **Python 3.11+** -- for the MCP server and CLI
- **git** -- for diff analysis and branch detection
- **uv** -- recommended Python package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh` or see [install docs](https://docs.astral.sh/uv/getting-started/installation/))
- An **MCP-capable coding agent** (e.g., Claude Code)

## Install the CLI

The simplest way to install is as a global tool via `uv`:

```bash
uv tool install git+https://github.com/jdraines/specmap.git
```

This makes the `specmap` command available everywhere:

```bash
specmap status
specmap validate
```

### Alternative: run without installing

Use `uvx` to run specmap commands without a permanent install:

```bash
uvx --from 'specmap @ git+https://github.com/jdraines/specmap.git' specmap status
```

### Alternative: add as a Python project dependency

If your project uses Python, add specmap to your dependencies:

=== "pyproject.toml"

    ```toml
    [project]
    dependencies = [
        "specmap @ git+https://github.com/jdraines/specmap.git",
    ]
    ```

=== "requirements.txt"

    ```
    specmap @ git+https://github.com/jdraines/specmap.git
    ```

Then `specmap` is available in your project's virtualenv.

## Add the MCP Server to Your Coding Agent

### Claude Code

Create or edit `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "specmap": {
      "command": "uvx",
      "args": [
        "--from", "specmap @ git+https://github.com/jdraines/specmap.git",
        "python", "-m", "specmap.mcp"
      ],
      "env": {
        "SPECMAP_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

If you installed specmap as a `uv tool`, you can use the simpler form:

```json
{
  "mcpServers": {
    "specmap": {
      "command": "specmap-mcp",
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

Specmap uses the standard MCP stdio transport. Any client that supports stdio-based MCP servers can connect. The server is started by running the `specmap.mcp` module:

```bash
uvx --from 'specmap @ git+https://github.com/jdraines/specmap.git' python -m specmap.mcp
```

## Verify Installation

```bash
specmap --version   # specmap 0.1.0
specmap --help      # Available commands and global flags
```
