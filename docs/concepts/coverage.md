# Coverage

Spec coverage measures how much of your changed code has been mapped to spec requirements. It's the core metric that Specmap enforces in CI.

## Definition

```
coverage = mapped changed lines / total changed lines
```

Both values are computed against the **base branch** (typically `main`) using `git diff`.

## Per-File and Overall

Coverage is calculated at two levels:

- **Per-file** — each changed file gets its own coverage ratio
- **Overall** — total mapped lines across all files / total changed lines across all files

The `specmap check` command reports both, and the `--threshold` flag applies to the overall coverage.

## How It's Calculated

1. **Get changed files** — run `git diff -U0 base...HEAD` to find all files with changes and their exact line ranges.

2. **Load mappings** — read `.specmap/{branch}.json` to get all code targets (file + line range).

3. **Intersect** — for each changed file, check which changed line ranges overlap with mapped code targets. A changed line is "mapped" if any mapping's `code_target` covers it.

4. **Compute ratio** — divide mapped changed lines by total changed lines.

**Special case:** if there are no changed files (e.g., the branch is identical to the base), coverage is `1.0` (100%) — there's nothing to cover.

## Stale Mappings

A mapping whose `content_hash` no longer matches the current code is marked **stale**. Stale mappings are:

- **Reported** by `specmap check` in the stale section
- **Not counted** toward coverage — stale mappings don't cover lines

This means coverage can drop after code edits even if the mapping still exists, because the mapping is stale until reindexed.

To fix stale mappings, run `specmap_reindex` via your coding agent.

## Threshold Enforcement

The `--threshold` flag on `specmap check` sets the minimum acceptable coverage:

```bash
# Require at least 80% coverage
specmap check --threshold 0.80
```

| Coverage | Threshold | Result | Exit code |
|---|---|---|---|
| 0.85 | 0.80 | PASS | 0 |
| 0.75 | 0.80 | FAIL | 1 |
| 1.00 | 0.00 | PASS | 0 |

### Recommended Thresholds

| Stage | Threshold | Rationale |
|---|---|---|
| Early adoption | `0.50` | Get the workflow going without blocking PRs |
| Established | `0.80` | Most code should have spec coverage |
| Strict | `0.95` | Nearly everything must be spec-mapped |

Start low and ratchet up as your team builds the habit of writing specs alongside code.
