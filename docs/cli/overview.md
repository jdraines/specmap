# CLI Overview

The Specmap CLI (built with Typer) is the primary command-line interface for all specmap operations: generating annotations, running the web UI, validating in CI, and managing configuration.

## Commands

| Command | Purpose | Makes LLM calls? |
|---|---|---|
| [`annotate`](commands.md#annotate) | Generate annotations with spec references | Yes |
| [`serve`](commands.md#serve) | Launch the web UI and API server | Yes (for walkthroughs, code review, chat) |
| [`validate`](commands.md#validate) | Check annotation line ranges are valid | No |
| [`status`](commands.md#status) | Show annotation summary | No |
| [`config`](commands.md#config) | Read and write configuration | No |
| [`hook`](commands.md#hook) | Manage git hooks | No |

## Global Flags

| Flag | Default | Description |
|---|---|---|
| `--repo-root` | Auto-detect from `.git/` | Path to repository root |
| `--branch` | Current git branch | Branch name for the specmap file |
| `--no-color` | `false` | Disable color output |
| `--version` | -- | Show version and exit |

Color output is automatically disabled when stdout is not a terminal.

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success (all checks pass) |
| `1` | Failure (validation errors, missing repo, etc.) |

## Running

If installed as a tool (`pip install specmap` or `uv tool install`):

```bash
specmap <command> [flags]
```

Or without installing:

```bash
uvx --from 'specmap @ git+https://github.com/jdraines/specmap.git' \
  specmap <command> [flags]
```
