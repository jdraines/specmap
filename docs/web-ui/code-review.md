# AI Code Review

The code review feature analyzes a PR's changes and produces structured, actionable issues with severity ratings, suggested fixes, and per-issue chat.

## Generating a Code Review

Open a PR in the web UI, then click **Code Review** in the toolbar. Optional parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| Max issues | -- | Limit the number of issues returned |
| Context lines | -- | Lines of surrounding context to include |
| Custom prompt | -- | Additional instructions for the reviewer (e.g., "focus on security") |

Click **Generate** to start. The review pipeline runs in three phases, with progress streamed in real-time.

### Review Pipeline

1. **File-level review** -- each changed file is analyzed independently for issues. Files are processed in parallel for speed.
2. **Cross-boundary check** -- a second pass looks for cross-file wiring issues: changed function signatures with unchecked callers, renamed exports with stale imports, modified type definitions with unconverted consumers.
3. **Consolidation** -- duplicates are merged, false positives pruned, and all issues get final severity ratings.

## Severity Ratings

Issues are rated on a P0-P4 scale:

| Severity | Meaning | Action |
|----------|---------|--------|
| **P0** | Blocks merge | Correctness bug, security vulnerability, data loss risk |
| **P1** | Should fix before merge | Significant logic error, missing error handling, API contract violation |
| **P2** | Should fix soon | Edge case handling, suboptimal design, missing boundary validation |
| **P3** | Consider fixing | Minor improvement, better naming, small refactoring opportunity |
| **P4** | Nit | Style preference, optional cleanup |

P0 and P1 issues undergo extra self-verification: the reviewer must quote the exact problematic lines, trace a concrete triggering input, and confirm no existing guard clause prevents the issue. If it can't construct a real trigger, it drops the issue rather than downgrading.

## Review Dimensions

The reviewer adapts focus to the content of the diff:

- **Correctness** -- logic errors, off-by-one, unhandled error paths, race conditions
- **Security** -- injection vulnerabilities, auth gaps, data exposure, insecure defaults
- **Performance** -- N+1 queries, unnecessary allocations, blocking in async code
- **Design** -- coupling issues, abstraction mismatches, breaking API changes
- **Frontend** -- accessibility, XSS, state management, missing error boundaries
- **Cross-codebase wiring** -- changed signatures with unchecked callers, stale imports after renames

## Reading Issues

Each issue includes:

- **Severity** (P0-P4) and **title**
- **File and line range** -- clicking navigates to the issue location in the diff
- **Description** -- what the problem is and why it matters
- **Suggested fix** -- concrete code suggestion when possible

Issues are ordered by severity (P0 first), then by narrative flow within the same severity level.

## Per-Issue Chat

At each issue, you can open the chat to discuss it with the AI assistant. The chat agent has the same codebase investigation tools as the [walkthrough chat](walkthroughs.md#per-step-chat):

- `search_annotations` -- search PR annotations
- `grep_codebase` -- regex search across the repo
- `list_files` -- browse the file tree
- `read_file` -- read file content with diffs

The agent thinks critically -- if its investigation contradicts the original issue, it says so directly rather than deferring to the prior analysis.

## Dismissing Issues

If an issue is a false positive or not actionable, click the dismiss button to hide it. Dismissed issues are tracked per PR and won't reappear when switching between issues.

## Tips

- Use the **custom prompt** to focus the review on specific concerns (e.g., "focus on SQL injection risks" or "check that all new endpoints require authentication")
- For large PRs, the reviewer processes files in parallel to keep generation fast
- Issues only flag lines that appear in the diff, not unchanged context lines
