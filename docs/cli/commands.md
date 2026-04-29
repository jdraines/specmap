# Commands Reference

## annotate

Generates annotations for code changes using an LLM. Each annotation is a natural-language description of a code region with `[N]` inline citations referencing spec locations.

### Usage

```bash
specmap annotate [FILES] [flags]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `FILES` | Specific files to annotate (default: all changed files) |

### Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--context` | -- | Freeform development context for better annotations |
| `--dry-run` | `false` | Show what would be regenerated without making LLM calls |
| `--json` | `false` | Output raw JSON |

### Examples

```bash
# Annotate all changes on the current branch
specmap annotate

# Annotate specific files
specmap annotate src/auth.py src/session.py

# Provide context for better annotations
specmap annotate --context "Implementing OAuth2 token refresh"

# Preview what would change (no LLM calls)
specmap annotate --dry-run

# Machine-readable output
specmap annotate --json
```

### Output

Normal output shows a summary:

```
Annotations: 3 created, 12 total
Spec files used: 2
Code changes analyzed: 4
Incremental: 8 kept, 1 shifted, 3 regenerated
LLM: 2 calls, 2450 in / 380 out tokens
```

With `--dry-run`:

```
Dry run — no LLM calls or file changes made.

Would keep:       8
Would shift:      1
Would regenerate: 3

Annotations to regenerate:
  auth/session.go L15-42  (a_a1b2c3d4e5f6)
  auth/session.go L44-61  (a_b2c3d4e5f6a7)
  auth/hash.go L8-23      (a_c3d4e5f6a7b8)

Files: auth/session.go, auth/hash.go
```

---

## serve

Starts the specmap API server with the embedded React frontend. Auto-opens a browser when a frontend is available.

On first run, if no LLM API key is configured, the server prompts interactively for one and optionally saves it to user config.

### Usage

```bash
specmap serve [flags]
```

### Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--port` | `8080` | Port to listen on (auto-increments if in use) |
| `--host` | `127.0.0.1` | Host to bind to |
| `--db` | `.specmap/specmap.db` | SQLite database path |
| `--static-dir` | *(auto)* | Directory with built frontend files (overrides bundled frontend) |
| `--reload` | `false` | Enable auto-reload for development |
| `--no-open` | `false` | Don't auto-open the browser |

### Static File Resolution

The frontend is resolved in this order:

1. `--static-dir` flag (explicit path)
2. `STATIC_DIR` environment variable
3. Bundled `_static/` directory (included in the pip package)

If none are found, the server runs as an API-only backend (no browser auto-open).

### Examples

```bash
# Typical local use — browser opens automatically
specmap serve

# Suppress browser auto-open
specmap serve --no-open

# Bind to all interfaces (Docker / remote access)
specmap serve --host 0.0.0.0

# Development with auto-reload
specmap serve --reload --no-open

# Use a custom frontend build
specmap serve --static-dir ../web/dist
```

---

## validate

Checks the structural validity of `.specmap/{branch}.json` by verifying that all annotated line ranges exist in the current code files.

### Usage

```bash
specmap validate [flags]
```

### Flags

Inherits [global flags](overview.md#global-flags) only.

### What It Checks

- **File existence** -- verifies that each annotated file exists in the repo
- **Line range validity** -- verifies that `start_line` and `end_line` are within the file's actual line count
- **Schema validity** -- verifies the specmap file conforms to the v2 schema

### Example Output

```
[ok] auth/session.go:15-42 valid
[ok] auth/session.go:44-61 valid
[ok] auth/hash.go:8-23 valid
[err] auth/old.go:10-25 file not found

Validation: 3/4 passed
```

Exits with code 1 if any validation errors are found.

---

## status

Displays a human-readable summary of the current branch's annotations.

### Usage

```bash
specmap status [flags]
```

### Flags

Inherits [global flags](overview.md#global-flags) only.

### Example Output

```
Branch: feature/add-auth (base: main)
Head SHA: a1b2c3d4

Annotations: 12 total across 5 files

  auth/session.go (3 annotations)
    :15-42  Implements JWT session token creation and validation with
            httpOnly cookie storage [1] and 24-hour expiry [2].
    :44-61  Handles token refresh middleware that silently renews
            expired tokens on each API request [1].
    :63-78  Session cleanup on explicit logout [1].

  auth/hash.go (2 annotations)
    :8-23   Bcrypt password hashing with cost factor 12 [1].
    :25-40  Password verification with constant-time comparison [1].

  ...

Annotations: 10/12 have spec refs
```

---

## config

Read and write specmap configuration. Uses dot-notation keys that map to TOML sections.

### Subcommands

#### config list

Show all resolved configuration values with their source (env, repo, user, or default):

```bash
specmap config list
```

```
defaults.annotate_timeout = 120  (default)
defaults.batch_token_budget = 8000  (default)
forge.github.token = ghp_abc****  (env)
llm.api_key = sk-ant-****  (user)
llm.model = gpt-4o-mini  (default)
repo.base_branch = main  (repo)
repo.spec_patterns = ['**/*.md']  (default)
...
```

#### config get

Print the resolved value for a single key:

```bash
specmap config get llm.model
```

#### config set

Write a value to user config (default) or repo config (`--repo`):

```bash
# Set in user config (secrets allowed)
specmap config set llm.api_key sk-ant-...

# Set in repo config (secrets blocked)
specmap config set --repo repo.base_branch develop
```

Secrets (`llm.api_key`, `forge.github.token`, `forge.gitlab.token`) are blocked from repo config to prevent accidental commits.

#### config path

Print the paths to user and repo config files:

```bash
specmap config path
```

#### config edit

Open the config file in `$EDITOR` (or `vi`):

```bash
specmap config edit          # user config
specmap config edit --repo   # repo config
```

#### config migrate

Migrate a legacy `.specmap/config.json` to TOML config files:

```bash
specmap config migrate
```

Secrets are written to user config, repo settings to repo config. The original JSON file is renamed to `.json.bak`.

### Valid Keys

| Key | Type | Description |
|-----|------|-------------|
| `llm.model` | string | LLM model identifier |
| `llm.api_key` | string | API key (user config only) |
| `llm.api_base` | string | Custom API base URL |
| `forge.github.token` | string | GitHub PAT (user config only) |
| `forge.gitlab.token` | string | GitLab token (user config only) |
| `repo.spec_patterns` | list | Glob patterns for spec files |
| `repo.ignore_patterns` | list | Glob patterns for files to ignore |
| `repo.base_branch` | string | Branch to diff against |
| `defaults.batch_token_budget` | int | Max tokens per LLM batch |
| `defaults.annotate_timeout` | int | Annotation timeout in seconds |
| `server.host` | string | Server bind address |
| `server.port` | int | Server port |
| `server.database_path` | string | SQLite database path |

---

## hook

Manage git hooks for automatic annotation generation.

### hook install

Install a post-commit hook that runs `specmap annotate --json` in the background after each commit:

```bash
specmap hook install
```

If a non-specmap post-commit hook already exists, the command prints instructions for manual integration instead of overwriting it.

### hook uninstall

Remove the specmap post-commit hook:

```bash
specmap hook uninstall
```

If the hook contains non-specmap content, only the specmap section is removed.

### hook status

Check if the specmap post-commit hook is installed:

```bash
specmap hook status
```
