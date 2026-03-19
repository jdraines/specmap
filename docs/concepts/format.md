# Specmap Format

Specmap stores mapping data in `.specmap/{branch}.json` within the repository. This file is committed to git alongside the code it describes.

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
  "version": 1,
  "branch": "feature/add-auth",
  "base_branch": "main",
  "updated_at": "2025-01-15T10:30:00Z",
  "updated_by": "mcp:claude-code",
  "spec_documents": {
    "docs/auth.md": {
      "doc_hash": "sha256:a1b2c3d4e5f6a7b8",
      "sections": {
        "Authentication > Token Storage": {
          "heading_path": ["Authentication", "Token Storage"],
          "heading_line": 5,
          "section_hash": "sha256:c3d4e5f6a7b8c9d0"
        },
        "Authentication > Password Hashing": {
          "heading_path": ["Authentication", "Password Hashing"],
          "heading_line": 12,
          "section_hash": "sha256:e5f6a7b8c9d0e1f2"
        }
      }
    }
  },
  "mappings": [
    {
      "id": "m_a1b2c3d4e5f6",
      "spec_spans": [
        {
          "spec_file": "docs/auth.md",
          "heading_path": ["Authentication", "Token Storage"],
          "span_offset": 45,
          "span_length": 120,
          "span_hash": "sha256:1a2b3c4d5e6f7a8b",
          "relevance": 0.95
        }
      ],
      "code_target": {
        "file": "auth/session.go",
        "start_line": 15,
        "end_line": 42,
        "content_hash": "sha256:9a8b7c6d5e4f3a2b"
      },
      "stale": false,
      "created_at": "2025-01-15T10:30:00Z"
    }
  ],
  "ignore_patterns": ["*.generated.go", "*.lock", "vendor/**"]
}
```

## Field Reference

### Top-Level Fields

| Field | Type | Description |
|---|---|---|
| `version` | `int` | Schema version (currently `1`) |
| `branch` | `string` | Branch this file tracks |
| `base_branch` | `string` | Branch to diff against (default: `main`) |
| `updated_at` | `datetime` | Last modification timestamp (UTC) |
| `updated_by` | `string` | What created/updated the file (e.g., `mcp:claude-code`) |
| `spec_documents` | `object` | Indexed spec files, keyed by relative path |
| `mappings` | `array` | List of spec-to-code mappings |
| `ignore_patterns` | `string[]` | Glob patterns for files to exclude from coverage |

### Spec Document

| Field | Type | Description |
|---|---|---|
| `doc_hash` | `string` | SHA-256 hash of the full file content |
| `sections` | `object` | Sections keyed by joined heading path (e.g., `"Auth > Token Storage"`) |

### Spec Section

| Field | Type | Description |
|---|---|---|
| `heading_path` | `string[]` | Nested heading hierarchy (e.g., `["Auth", "Token Storage"]`) |
| `heading_line` | `int` | Line number of the heading in the spec file |
| `section_hash` | `string` | Hash of the section content (heading to next same-level heading) |

### Mapping

| Field | Type | Description |
|---|---|---|
| `id` | `string` | Unique identifier (`m_` + 12 hex chars) |
| `spec_spans` | `array` | One or more spec text spans this mapping references |
| `code_target` | `object` | The code region this mapping covers |
| `stale` | `bool` | `true` if hashes no longer match (needs reindex) |
| `created_at` | `datetime` | When the mapping was created |

### Spec Span

| Field | Type | Description |
|---|---|---|
| `spec_file` | `string` | Relative path to the spec file |
| `heading_path` | `string[]` | Section the span is within |
| `span_offset` | `int` | Character offset from section start |
| `span_length` | `int` | Character length of the span |
| `span_hash` | `string` | Hash of the span text |
| `relevance` | `float` | LLM-assigned relevance score (0.0–1.0) |

### Code Target

| Field | Type | Description |
|---|---|---|
| `file` | `string` | Relative path to the source file |
| `start_line` | `int` | First line of the code region (1-based, inclusive) |
| `end_line` | `int` | Last line of the code region (1-based, inclusive) |
| `content_hash` | `string` | Hash of the code content in this range |

## Design Invariant

The specmap file contains **only hashes and pointers** — never raw text from spec documents or source code. This keeps the file compact and ensures the actual files remain the single source of truth.
