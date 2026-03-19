# CLI Overview

The Specmap CLI is a Python tool (built with Typer) that validates spec-to-code mappings and enforces coverage thresholds. It reads `.specmap/{branch}.json` files and git diffs — it never makes LLM calls or network requests.

## What It Does

- **`validate`** — checks hash integrity of all mappings
- **`status`** — shows a human-readable summary of specs, mappings, and staleness
- **`check`** — computes coverage against a base branch and enforces a threshold

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
| `0` | Success (all checks pass, coverage meets threshold) |
| `1` | Failure (validation errors, coverage below threshold) |

## Running

```bash
cd core
uv run python -m specmap.cli <command> [flags]
```

Or with just:

```bash
just cli-run <command> [flags]
```
