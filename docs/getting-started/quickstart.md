# Quick Start

This guide covers three ways to use specmap. Choose the approach that fits your workflow.

## Step 1: Install Specmap

```bash
pip install specmap
```

This gives you two commands: `specmap` (CLI) and `specmap-mcp` (MCP server).

See [Installation](installation.md) for alternative install methods.

## Step 2: Write a Spec

Create a markdown spec file in your repo. Specmap auto-discovers `**/*.md` files (excluding `README.md`, `CHANGELOG.md`, and similar).

```markdown
# Authentication

## Token Storage

Sessions use signed JWTs stored in httpOnly cookies.
Tokens expire after 24 hours and are refreshed silently
on each API request.

## Password Hashing

All passwords are hashed with bcrypt (cost factor 12)
before storage. Plain-text passwords are never persisted.
```

## Step 3: Generate Annotations

=== "Web UI"

    Launch the web UI to review PRs with annotations, walkthroughs, and code reviews:

    ```bash
    specmap serve
    ```

    The browser opens automatically. On first run, you'll be prompted for an LLM API key if one isn't configured.

    From the dashboard, navigate to a PR. Then:

    - **Generate Annotations** -- click in the toolbar to create spec-linked annotations for the PR's changes
    - **Walkthrough** -- generate an AI-guided narrative tour of the PR
    - **Code Review** -- run an AI code review with severity ratings and suggested fixes

    The web UI needs a forge token (GitHub PAT or GitLab token) to fetch repository data. See [Web UI Overview](../web-ui/overview.md) for authentication details.

=== "MCP + Agent"

    Add the MCP server to your coding agent. In your project's `.mcp.json`:

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

    Start coding on a feature branch. As your agent writes code, it calls `specmap_annotate` automatically to create annotations linking code changes to spec requirements.

    Behind the scenes, the MCP server:

    1. Runs `git diff` to find changed code
    2. Reads the spec files in the repo
    3. Sends the diff and specs to the LLM, which generates annotations with `[N]` spec citations
    4. Writes annotations to `.specmap/{branch}.json`

    By default, Specmap uses `gpt-4o-mini`. See [Configuration](configuration.md) to use a different model or provider.

=== "CLI"

    Generate annotations directly from the command line:

    ```bash
    # Set your LLM API key
    export SPECMAP_API_KEY="sk-..."

    # Annotate all changes on the current branch
    specmap annotate

    # Or annotate specific files
    specmap annotate src/auth.py src/session.py
    ```

    This generates `.specmap/{branch}.json` containing annotations with `[N]` spec citations.

    You can also install a git hook to annotate automatically on every commit:

    ```bash
    specmap hook install
    ```

## Step 4: Check Status

Review what's been annotated:

```bash
specmap status
```

```
Branch: feature/add-auth (base: main)
Head SHA: a1b2c3d4

Annotations: 3 total across 2 files

  auth/session.go (2 annotations)
    :15-42  Implements JWT session token creation with httpOnly
            cookie storage [1] and 24-hour expiry [2].
    :44-61  Handles silent token refresh on API requests [1].

  auth/hash.go (1 annotation)
    :8-23   Bcrypt password hashing with cost factor 12 [1].
```

Validate that all line ranges are still valid:

```bash
specmap validate
```

```
[ok] auth/session.go:15-42 valid
[ok] auth/session.go:44-61 valid
[ok] auth/hash.go:8-23 valid

Validation: 3/3 passed
```

Commit the `.specmap/` directory with your code and push. For CI integration, see [CI Integration](../cli/ci.md).
