# CI Integration

The `specmap validate` command can be used in CI pipelines to verify that annotations are structurally valid — all annotated files exist and line ranges are within bounds.

## GitHub Actions Example

```yaml
name: Specmap Validate

on:
  pull_request:
    branches: [main]

jobs:
  specmap-validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Full history needed for git diff

      - uses: astral-sh/setup-uv@v5

      - name: Validate annotations
        run: |
          uvx --from 'specmap @ git+https://github.com/jdraines/specmap.git#subdirectory=core' \
            specmap --no-color validate
```

## Key Flags for CI

| Flag | Purpose |
|---|---|
| `--no-color` | Clean log output without ANSI escape codes |

## Exit Codes

| Code | CI Result | Meaning |
|---|---|---|
| `0` | Pass | All annotations are structurally valid |
| `1` | Fail | Validation errors found (missing files, invalid line ranges) |

## Tips

!!! tip "Fetch full history"
    Use `fetch-depth: 0` in your checkout step to ensure the full commit history is available.

!!! note "Phase 4: GitHub Action"
    A dedicated `specmap-action` GitHub Action is planned for Phase 4, which will simplify setup and add PR comment integration.
