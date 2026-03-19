# Tools Reference

The MCP server exposes four tools. All parameters are optional — the server auto-detects sensible defaults from the git repo.

## specmap_map

Creates mappings between code changes and spec sections using an LLM.

**When to use:** After writing or modifying code, to record which spec requirements the changes implement.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `repo_root` | `string` | Auto-detect from `.git/` | Path to repository root |
| `code_changes` | `string[]` | Auto-detect from `git diff` | File paths to analyze |
| `spec_files` | `string[]` | Auto-discover from glob patterns | Spec files to map against |
| `branch` | `string` | Current git branch | Branch name for the specmap file |

### Output

```json
{
  "status": "ok",
  "mappings_created": 3,
  "mappings_updated": 1,
  "total_mappings": 12,
  "spec_files_parsed": 2,
  "code_changes_analyzed": 4,
  "llm_usage": {
    "total_input_tokens": 2450,
    "total_output_tokens": 380,
    "total_calls": 2
  },
  "branch": "feature/add-auth"
}
```

**Status values:** `ok` (mappings created), `no_specs` (no spec files found), `no_changes` (no code changes detected).

---

## specmap_check

Verifies that existing mappings are still valid by checking hashes against current file contents.

**When to use:** To see if any mappings have become stale after code or spec edits.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `repo_root` | `string` | Auto-detect | Path to repository root |
| `branch` | `string` | Current branch | Branch name |
| `files` | `string[]` | All mapped files | Specific files to check |

### Output

```json
{
  "status": "ok",
  "valid": 10,
  "relocated": 2,
  "stale": 1,
  "total": 13,
  "stale_details": [
    {
      "mapping_id": "m_a1b2c3d4e5f6",
      "code_file": "auth/session.go",
      "code_lines": "15-42",
      "spec_spans": ["docs/auth.md (Authentication > Token Storage)"]
    }
  ]
}
```

---

## specmap_unmapped

Reports coverage per file — which changed lines have mappings and which don't.

**When to use:** To find gaps in spec coverage before opening a PR.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `repo_root` | `string` | Auto-detect | Path to repository root |
| `branch` | `string` | Current branch | Branch name |
| `base_branch` | `string` | From specmap file | Base branch for diff |
| `threshold` | `number` | — | Only report files below this coverage (0.0–1.0) |

### Output

```json
{
  "status": "ok",
  "overall_coverage": 0.82,
  "total_changed_lines": 298,
  "mapped_lines": 245,
  "unmapped_lines": 53,
  "files": {
    "auth/middleware.go": {
      "changed_lines": 38,
      "mapped_lines": 0,
      "unmapped_lines": 38,
      "coverage": 0.0,
      "unmapped_ranges": [{"start": 1, "end": 38}]
    },
    "auth/session.go": {
      "changed_lines": 65,
      "mapped_lines": 65,
      "unmapped_lines": 0,
      "coverage": 1.0,
      "unmapped_ranges": []
    }
  }
}
```

---

## specmap_reindex

Re-indexes mappings after specs or code have changed. Uses hierarchical hashing to minimize work — only re-examines documents, sections, or spans whose hashes differ.

**When to use:** After editing spec documents or refactoring code, to update mappings without re-mapping from scratch.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `repo_root` | `string` | Auto-detect | Path to repository root |
| `spec_files` | `string[]` | All specs | Specific spec files to re-index |
| `code_files` | `string[]` | All mapped code | Specific code files to re-index |
| `force` | `boolean` | `false` | Re-index everything regardless of hash changes |

### Output

```json
{
  "status": "ok",
  "unchanged": 8,
  "relocated": 3,
  "stale": 1,
  "remapped": 2,
  "docs_skipped": 1,
  "sections_skipped": 4,
  "total_mappings": 14
}
```

**Field meanings:**

- `unchanged` — mappings whose hashes still match (no work needed)
- `relocated` — mappings found at a different offset via exact or fuzzy match
- `stale` — mappings that could not be relocated (marked stale)
- `remapped` — mappings that required an LLM call to re-establish
- `docs_skipped` / `sections_skipped` — skipped because their hashes didn't change
