# Configuration

Specmap loads configuration from three sources, applied in priority order.

## Config Sources

| Priority | Source | Location |
|---|---|---|
| 1 (highest) | Environment variables | `SPECMAP_*` in shell environment |
| 2 | Repo config | `.specmap/config.toml` in repo root |
| 3 | User config | `~/.config/specmap/config.toml` (or `$XDG_CONFIG_HOME/specmap/config.toml`) |
| 4 | Defaults | Built into specmap |

## All Options

| Environment Variable | Config Key | Default | Description |
|---|---|---|---|
| `SPECMAP_MODEL` | `llm.model` | `gpt-4o-mini` | LLM model identifier (any litellm-supported model) |
| `SPECMAP_API_KEY` | `llm.api_key` | -- | API key for LLM provider (required for AI features) |
| `SPECMAP_API_BASE` | `llm.api_base` | -- | Custom API base URL (for proxies, local models) |
| `SPECMAP_SPEC_PATTERNS` | `repo.spec_patterns` | `**/*.md` | Comma-separated glob patterns for spec files |
| `SPECMAP_IGNORE_PATTERNS` | `repo.ignore_patterns` | `*.generated.go,*.lock,vendor/**` | Comma-separated patterns for files to ignore |
| `SPECMAP_BASE_BRANCH` | `repo.base_branch` | Auto-detect (`main` → `master`) | Branch to diff against when generating annotations |
| `SPECMAP_BATCH_TOKEN_BUDGET` | `defaults.batch_token_budget` | `8000` | Max tokens per LLM batch |
| `SPECMAP_ANNOTATE_TIMEOUT` | `defaults.annotate_timeout` | `120` | Seconds before annotation generation times out |

Forge tokens and server settings are also configurable:

| Environment Variable | Config Key | Description |
|---|---|---|
| `GITHUB_TOKEN` / `GH_TOKEN` | `forge.github.token` | GitHub personal access token |
| `GITLAB_TOKEN` | `forge.gitlab.token` | GitLab personal access token |
| `HOST` | `server.host` | Server bind address (default: `127.0.0.1`) |
| `PORT` | `server.port` | Server port (default: `8080`) |
| `DATABASE_PATH` | `server.database_path` | SQLite database path (default: `.specmap/specmap.db`) |

## Config File Format

Specmap uses TOML config files organized into sections:

```toml
[llm]
model = "gpt-4o-mini"
api_key = "sk-..."        # user config only — blocked in repo config
api_base = "https://..."  # optional, for proxies or local models

[forge]
github_token = "ghp_..."  # user config only
gitlab_token = "glpat-..."  # user config only

[repo]
spec_patterns = ["**/*.md"]
ignore_patterns = ["*.generated.go", "*.lock", "vendor/**"]
base_branch = "main"

[defaults]
batch_token_budget = 8000
annotate_timeout = 120

[server]
host = "127.0.0.1"
port = 8080
database_path = ".specmap/specmap.db"
```

!!! danger "Security: secrets in config files"
    `llm.api_key`, `forge.github.token`, and `forge.gitlab.token` are **blocked in repo config** (`.specmap/config.toml`) to prevent accidental commits. Store secrets in user config (`~/.config/specmap/config.toml`) or environment variables.

!!! note "Migrating from JSON config"
    If you have an existing `.specmap/config.json`, specmap still reads it but prints a deprecation warning. Run `specmap config migrate` to automatically split it into user and repo TOML files. Secrets go to user config; repo settings go to repo config. The original JSON file is renamed to `.json.bak`.

## Managing Config via CLI

The `specmap config` command reads and writes configuration using dot-notation keys:

```bash
# Show all resolved values with their sources
specmap config list

# Get a single value
specmap config get llm.model

# Set a value (writes to user config by default)
specmap config set llm.model claude-sonnet-4-20250514

# Set a value in repo config (secrets are blocked)
specmap config set --repo repo.base_branch develop

# Show config file paths
specmap config path

# Open config in $EDITOR
specmap config edit
specmap config edit --repo

# Migrate from legacy JSON config
specmap config migrate
```

## Spec Auto-Discovery

When using the default `**/*.md` pattern, Specmap automatically excludes common non-spec files:

**Excluded filenames:**

- `README.md`
- `CHANGELOG.md`
- `CONTRIBUTING.md`
- `LICENSE.md`
- `CODE_OF_CONDUCT.md`

**Excluded directories:**

- `node_modules`
- `.git`
- `.specmap`
- `vendor`
- `__pycache__`
- `.venv` / `venv`

To override these defaults, set `SPECMAP_SPEC_PATTERNS` to explicit patterns:

```bash
export SPECMAP_SPEC_PATTERNS="docs/**/*.md,specs/**/*.md"
```

## Examples

### Use Anthropic Claude

```bash
export SPECMAP_MODEL="claude-sonnet-4-20250514"
export SPECMAP_API_KEY="sk-ant-..."
```

Or via config:

```bash
specmap config set llm.model claude-sonnet-4-20250514
specmap config set llm.api_key sk-ant-...
```

### Use a Local Model (via Ollama)

```bash
export SPECMAP_MODEL="ollama/llama3"
export SPECMAP_API_BASE="http://localhost:11434"
```

### Use Azure OpenAI

```bash
export SPECMAP_MODEL="azure/gpt-4o-mini"
export SPECMAP_API_KEY="your-azure-key"
export SPECMAP_API_BASE="https://your-resource.openai.azure.com"
```

### Use a Custom Base Branch

Teams using `develop`, `staging`, or other branches as their PR target can override the auto-detected base branch:

```bash
specmap config set --repo repo.base_branch develop
```

Or via environment variable:

```bash
export SPECMAP_BASE_BRANCH="develop"
```
