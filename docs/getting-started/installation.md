# Installation

## Prerequisites

- **Python 3.11+** -- for the CLI, MCP server, and API server
- **git** -- for diff analysis and branch detection

## Install from PyPI

```bash
pip install specmap
```

Or as a global tool via `uv`:

```bash
uv tool install specmap
```

This makes the `specmap` command available everywhere:

```bash
specmap --version   # specmap 0.4.0
specmap serve       # Launch the web UI
specmap annotate    # Generate annotations from CLI
specmap validate    # Validate annotations in CI
```

### Alternative: install from git

For the latest development version:

```bash
pip install git+https://github.com/jdraines/specmap.git
# or
uv tool install git+https://github.com/jdraines/specmap.git
```

### Alternative: run without installing

Use `uvx` to run specmap commands without a permanent install:

```bash
uvx --from specmap specmap status
```

### Alternative: add as a Python project dependency

If your project uses Python, add specmap to your dependencies:

=== "pyproject.toml"

    ```toml
    [project]
    dependencies = [
        "specmap",
    ]
    ```

=== "requirements.txt"

    ```
    specmap
    ```

Then `specmap` is available in your project's virtualenv.

## Set Up the MCP Server (Optional)

If you use a coding agent (e.g., Claude Code), add the MCP server for automatic annotation during development.

### Claude Code

Create or edit `.mcp.json` in your project root:

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

If you didn't install specmap as a tool, use the longer form:

```json
{
  "mcpServers": {
    "specmap": {
      "command": "uvx",
      "args": [
        "--from", "specmap",
        "python", "-m", "specmap.mcp"
      ],
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
python -m specmap.mcp
```

## Verify Installation

```bash
specmap --version   # specmap 0.4.0
specmap --help      # Available commands and global flags
```
