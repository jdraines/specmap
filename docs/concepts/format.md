# Specmap Format

Specmap stores annotation data in `.specmap/{branch}.json` within the repository. This file is committed to git alongside the code it describes.

## File Location

The filename is derived from the branch name with `/` replaced by `--`:

| Branch | File |
|---|---|
| `main` | `.specmap/main.json` |
| `feature/add-auth` | `.specmap/feature--add-auth.json` |
| `fix/token-expiry` | `.specmap/fix--token-expiry.json` |

## Full Schema

```json
{
  "version": 2,
  "branch": "feature/add-auth",
  "base_branch": "main",
  "head_sha": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
  "updated_at": "2025-01-15T10:30:00Z",
  "updated_by": "mcp:claude-code",
  "annotations": [
    {
      "id": "a_a1b2c3d4e5f6",
      "file": "auth/session.go",
      "start_line": 15,
      "end_line": 42,
      "description": "Implements JWT session token creation and validation with httpOnly cookie storage [1] and 24-hour expiry with silent refresh [2].",
      "refs": [
        {
          "id": 1,
          "spec_file": "docs/auth.md",
          "heading": "Authentication > Token Storage",
          "start_line": 5,
          "excerpt": "Sessions use signed JWTs stored in httpOnly cookies"
        },
        {
          "id": 2,
          "spec_file": "docs/auth.md",
          "heading": "Authentication > Token Storage",
          "start_line": 7,
          "excerpt": "Tokens expire after 24 hours and are refreshed silently"
        }
      ],
      "created_at": "2025-01-15T10:30:00Z"
    }
  ],
  "ignore_patterns": ["*.generated.go", "*.lock", "vendor/**"],
  "file_hashes": {}
}
```

## Field Reference

### Top-Level Fields

| Field | Type | Description |
|---|---|---|
| `version` | `int` | Schema version (currently `2`) |
| `branch` | `string` | Branch this file tracks |
| `base_branch` | `string` | Branch to diff against (default: `main`) |
| `head_sha` | `string` | Git commit SHA that was last annotated; enables incremental diff optimization |
| `updated_at` | `datetime` | Last modification timestamp (UTC) |
| `updated_by` | `string` | What created/updated the file (e.g., `mcp:claude-code`) |
| `annotations` | `array` | List of code region annotations with spec references |
| `ignore_patterns` | `string[]` | Glob patterns for files to exclude from coverage |
| `file_hashes` | `object` | Map of file path → content hash, used for incremental diff tracking |

### Annotation

| Field | Type | Description |
|---|---|---|
| `id` | `string` | Unique identifier (`a_` + 12 hex chars) |
| `file` | `string` | Relative path to the source file |
| `start_line` | `int` | First line of the code region (1-based, inclusive) |
| `end_line` | `int` | Last line of the code region (1-based, inclusive) |
| `description` | `string` | Natural-language description with `[N]` inline citations referencing the `refs` list |
| `refs` | `array` | List of spec references cited in the description |
| `created_at` | `datetime` | When the annotation was created |

### SpecRef

| Field | Type | Description |
|---|---|---|
| `id` | `int` | Citation number used in the description (e.g., `[1]`) |
| `spec_file` | `string` | Relative path to the spec file |
| `heading` | `string` | Section heading path in the spec (e.g., `"Auth > Token Storage"`) |
| `start_line` | `int` | Line number in the spec file where the referenced text begins |
| `excerpt` | `string` | Short excerpt of the referenced spec text |

## Coverage Semantics

The `refs` list determines coverage:

- **Annotations with non-empty `refs`** -- the code region is spec-covered. These lines count toward coverage.
- **Annotations with empty `refs`** -- the code region is described but not linked to any spec. These lines are not counted as covered.
- **Changed lines with no annotation** -- unmapped. Not counted as covered.

## Design Principles

The specmap file contains annotations with short excerpts for context, but the spec documents and source files remain the single source of truth. The `head_sha` field enables incremental updates -- only changes since the last annotated commit need to be processed on subsequent pushes.
