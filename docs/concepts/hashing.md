# Diff-Based Optimization

Specmap uses git diffs to detect changes efficiently and a hunk-level classification system to update annotations without unnecessary LLM calls.

## Two Diff Modes

Specmap operates in two modes depending on whether annotations already exist for the branch:

| Mode | When | Diff command | Scope |
|---|---|---|---|
| **First push** | No `head_sha` in specmap file | `git diff base_branch...HEAD` | All changed files vs. base branch |
| **Subsequent push** | `head_sha` present | `git diff {head_sha}..HEAD` | Only changes since last annotation |

## First Push

On the first push (or when no `.specmap/{branch}.json` exists), Specmap computes the full diff against the base branch:

1. Run `git diff base_branch...HEAD` to find all changed files and line ranges.
2. Read the spec files discovered in the repo.
3. Send the diff and specs to the LLM, which generates annotations: natural-language descriptions with `[N]` spec citations.
4. Write all annotations to `.specmap/{branch}.json` with the current `head_sha`.

## Subsequent Pushes

When `.specmap/{branch}.json` already exists and contains a `head_sha`, Specmap computes an incremental diff:

1. Run `git diff {previous_head_sha}..HEAD` to find only the new changes.
2. Classify each existing annotation into one of three categories:

### Annotation Classification

| Category | Condition | Action |
|---|---|---|
| **Keep** | Annotation's file has no changes in the incremental diff | No change needed |
| **Shift** | Annotation's file has changes, but the annotation's line range does not overlap with any diff hunk | Mechanically adjust `start_line` and `end_line` based on insertions/deletions above the annotation |
| **Regenerate** | Annotation's line range overlaps with a diff hunk | Discard and send to LLM for fresh annotation |

3. For regenerated annotations, send only the affected hunks and relevant specs to the LLM.
4. Update `head_sha` to the current commit.

## Why Diff-Based?

This approach makes annotation updates **proportional to the size of the incremental change**, not the total branch diff:

- A one-line fix? Only annotations overlapping that line are regenerated.
- A new file added? Only that file gets new annotations; existing annotations are untouched.
- A file reformatted? Annotations in that file are regenerated, but other files are unaffected.

This keeps updates fast and minimizes LLM costs, since most annotations are either kept as-is or mechanically shifted without any LLM involvement.

## Line Number Shifting

When code is inserted or deleted above an annotation, line numbers shift mechanically:

1. Parse the diff hunks for the annotation's file.
2. For each hunk that ends before the annotation's `start_line`, compute the net line change (lines added minus lines removed).
3. Apply the cumulative offset to both `start_line` and `end_line`.

This is a deterministic operation -- no LLM call is needed. Annotations are only regenerated when the diff hunk directly overlaps with the annotation's line range.
