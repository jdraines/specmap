# CI Integration

The `specmap check` command is designed for CI pipelines. It computes coverage, enforces a threshold, and returns a non-zero exit code on failure.

## GitHub Actions Example

```yaml
name: Specmap Coverage

on:
  pull_request:
    branches: [main]

jobs:
  specmap-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Full history needed for git diff

      - uses: astral-sh/setup-uv@v5

      - name: Install dependencies
        run: cd core && uv sync

      - name: Check spec coverage
        run: |
          cd core && uv run python -m specmap.cli \
            --no-color \
            check \
            --threshold 0.80 \
            --base origin/main
```

## Key Flags for CI

| Flag | Purpose |
|---|---|
| `--threshold 0.80` | Fail the build if coverage < 80% |
| `--base origin/main` | Explicit base branch (required in CI where auto-detect may not work) |
| `--no-color` | Clean log output without ANSI escape codes |
| `--json` | Machine-readable output for downstream processing |

## JSON Output for Scripting

Parse the JSON output to post coverage summaries as PR comments or feed into other tools:

```yaml
      - name: Check spec coverage (JSON)
        id: coverage
        run: |
          cd core && uv run python -m specmap.cli \
            --no-color \
            check \
            --threshold 0.80 \
            --base origin/main \
            --json > coverage.json

      - name: Post coverage summary
        if: always()
        run: |
          COVERAGE=$(jq '.coverage' coverage.json)
          echo "Spec coverage: ${COVERAGE}"
```

## Exit Codes

| Code | CI Result | Meaning |
|---|---|---|
| `0` | Pass | Coverage meets or exceeds threshold |
| `1` | Fail | Coverage below threshold, or validation errors |

## Tips

!!! tip "Fetch full history"
    The CLI runs `git diff base...HEAD` to determine changed files. Use `fetch-depth: 0` in your checkout step to ensure the full commit history is available.

!!! tip "Start with a low threshold"
    Begin with `--threshold 0.50` and ratchet up as your team adopts specmap. A threshold that's too high too early will block PRs.

!!! note "Phase 4: GitHub Action"
    A dedicated `specmap-action` GitHub Action is planned for Phase 4, which will simplify setup and add PR comment integration.
