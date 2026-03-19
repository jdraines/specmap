# Commands Reference

## validate

Checks the structural integrity of `.specmap/{branch}.json` by verifying all hashes against current file contents.

### Usage

```bash
specmap validate [flags]
```

### Flags

Inherits [global flags](overview.md#global-flags) only.

### What It Checks

- **Spec document hashes** (`doc_hash`) — re-hashes the spec file and compares
- **Code target hashes** (`content_hash`) — re-hashes the code line range and compares
- **Spec span hashes** (`span_hash`) — re-hashes the span text and compares

### Example Output

```
✓ docs/auth.md doc_hash valid
✓ auth/session.go:15-42 content_hash valid
✓ auth/session.go:44-61 content_hash valid
✗ auth/hash.go:8-23 content_hash MISMATCH
  expected: sha256:a1b2c3d4e5f6g7h8
  actual:   sha256:z9y8x7w6v5u4t3s2

Validation: 3/4 passed
```

Exits with code 1 if any hash mismatches are found.

---

## status

Displays a human-readable summary of the current branch's specmap state.

### Usage

```bash
specmap status [flags]
```

### Flags

Inherits [global flags](overview.md#global-flags) only.

### Example Output

```
Spec Documents:
  docs/auth.md (3 sections)
  docs/api.md (5 sections)

Mappings: 12 total, 10 valid, 2 stale
  auth/session.go:15-42  → auth.md > Authentication > Token Storage
  auth/session.go:44-61  → auth.md > Authentication > Token Storage
  auth/hash.go:8-23      → auth.md > Authentication > Password Hashing
  api/router.go:30-55    → api.md > Routes > User Endpoints
  ...

Stale mappings:
  ✗ auth/middleware.go:10-28 → auth.md > Authentication > Middleware
    (code content_hash mismatch)

Run 'specmap check' for coverage details.
```

---

## check

Computes spec coverage for the current branch against a base branch and optionally enforces a minimum threshold.

### Usage

```bash
specmap check [flags]
```

### Flags

| Flag | Default | Description |
|---|---|---|
| `--threshold` | `0.0` | Minimum coverage ratio (0.0–1.0). Exits 1 if below. |
| `--base` | From specmap file | Base branch for diff comparison |
| `--json` | `false` | Output JSON instead of human-readable text |

Plus [global flags](overview.md#global-flags).

### Human Output Example

```
specmap: checking coverage for feature/add-auth (base: main)
Files: 10/12 mapped | Lines: 245/298 mapped
Unmapped:
  auth/middleware.go (0%, 38 lines)
  hooks/useAuth.ts (0%, 15 lines)
Stale:
  auth/session.go:15-42 (hash mismatch)
Overall: 82.2% (threshold: 80.0%) — PASS
```

### JSON Output

Use `--json` for machine-readable output (useful in CI scripts):

```json
{
  "branch": "feature/add-auth",
  "base_branch": "main",
  "total_files": 12,
  "mapped_files": 10,
  "total_lines": 298,
  "mapped_lines": 245,
  "coverage": 0.822,
  "threshold": 0.80,
  "pass": true,
  "unmapped": [
    {
      "file": "auth/middleware.go",
      "coverage": 0.0,
      "total_lines": 38,
      "mapped_lines": 0
    }
  ],
  "stale": [
    {
      "file": "auth/session.go",
      "start_line": 15,
      "end_line": 42,
      "reason": "hash mismatch"
    }
  ]
}
```

### Exit Behavior

- Exits `0` if coverage >= threshold (or no threshold set)
- Exits `1` if coverage < threshold
- Both human and JSON modes respect the exit code
