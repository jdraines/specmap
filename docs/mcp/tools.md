# Tools Reference

The MCP server exposes two tools. All parameters are optional -- the server auto-detects sensible defaults from the git repo.

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
| `context` | `string` | -- | Optional freeform context from the development session (e.g. design decisions, constraints) that the LLM uses to write better descriptions |

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
