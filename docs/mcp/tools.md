# Tools Reference

The MCP server exposes three tools. All parameters are optional -- the server auto-detects sensible defaults from the git repo.

## specmap_annotate

Generates annotations for code changes using an LLM. Each annotation is a natural-language description of a code region with `[N]` inline citations referencing spec locations.

**When to use:** After writing or modifying code, to record which spec requirements the changes implement.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `repo_root` | `string` | Auto-detect from `.git/` | Path to repository root |
| `code_changes` | `string[]` | Auto-detect from `git diff` | File paths to analyze |
| `spec_files` | `string[]` | Auto-discover from glob patterns | Spec files to reference |
| `branch` | `string` | Current git branch | Branch name for the specmap file |

### Output

```json
{
  "status": "ok",
  "annotations_created": 3,
  "annotations_updated": 1,
  "annotations_kept": 8,
  "total_annotations": 12,
  "spec_files_read": 2,
  "code_changes_analyzed": 4,
  "llm_usage": {
    "total_input_tokens": 2450,
    "total_output_tokens": 380,
    "total_calls": 2
  },
  "branch": "feature/add-auth"
}
```

**Status values:** `ok` (annotations generated), `no_specs` (no spec files found), `no_changes` (no code changes detected).

---

## specmap_check

Verifies that existing annotations are still valid by checking that their line ranges exist in the current code files.

**When to use:** To see if any annotations have become invalid after code edits (e.g., file deleted, line range out of bounds).

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `repo_root` | `string` | Auto-detect | Path to repository root |
| `branch` | `string` | Current branch | Branch name |
| `files` | `string[]` | All annotated files | Specific files to check |

### Output

```json
{
  "status": "ok",
  "valid": 10,
  "invalid": 1,
  "total": 11,
  "invalid_details": [
    {
      "annotation_id": "ann_a1b2c3d4e5f6",
      "file": "auth/session.go",
      "start_line": 15,
      "end_line": 42,
      "reason": "file has only 30 lines"
    }
  ]
}
```

---

## specmap_unmapped

Reports coverage per file -- which changed lines have annotations with spec references and which don't.

**When to use:** To find gaps in spec coverage before opening a PR.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `repo_root` | `string` | Auto-detect | Path to repository root |
| `branch` | `string` | Current branch | Branch name |
| `base_branch` | `string` | From specmap file | Base branch for diff |
| `threshold` | `number` | -- | Only report files below this coverage (0.0-1.0) |

### Output

```json
{
  "status": "ok",
  "overall_coverage": 0.82,
  "total_changed_lines": 298,
  "covered_lines": 245,
  "uncovered_lines": 53,
  "files": {
    "auth/middleware.go": {
      "changed_lines": 38,
      "covered_lines": 0,
      "uncovered_lines": 38,
      "coverage": 0.0,
      "uncovered_ranges": [{"start": 1, "end": 38}]
    },
    "auth/session.go": {
      "changed_lines": 65,
      "covered_lines": 65,
      "uncovered_lines": 0,
      "coverage": 1.0,
      "uncovered_ranges": []
    }
  }
}
```
