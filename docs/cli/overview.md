# CLI Overview

The Specmap CLI is a Python tool (built with Typer) that validates annotations. It reads `.specmap/{branch}.json` files -- it never makes LLM calls or network requests.

## What It Does

- **`validate`** -- checks that annotated line ranges are valid in current code files
- **`status`** -- shows a human-readable summary of annotations with descriptions and file summaries

## Global Flags

| Flag | Default | Description |
|---|---|---|
| `--repo-root` | Auto-detect from `.git/` | Path to repository root |
| `--branch` | Current git branch | Branch name for the specmap file |
| `--no-color` | `false` | Disable color output |

Color output is automatically disabled when stdout is not a terminal (Rich auto-detection).

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success (all checks pass) |
| `1` | Failure (validation errors) |

## Running

```bash
cd core
uv run python -m specmap.cli <command> [flags]
```

Or with just:

```bash
just cli-run <command> [flags]
```
