# Commands Reference

## validate

Checks the structural validity of `.specmap/{branch}.json` by verifying that all annotated line ranges exist in the current code files.

### Usage

```bash
specmap validate [flags]
```

### Flags

Inherits [global flags](overview.md#global-flags) only.

### What It Checks

- **File existence** -- verifies that each annotated file exists in the repo
- **Line range validity** -- verifies that `start_line` and `end_line` are within the file's actual line count
- **Schema validity** -- verifies the specmap file conforms to the v2 schema

### Example Output

```
[ok] auth/session.go:15-42 valid
[ok] auth/session.go:44-61 valid
[ok] auth/hash.go:8-23 valid
[err] auth/old.go:10-25 file not found

Validation: 3/4 passed
```

Exits with code 1 if any validation errors are found.

---

## status

Displays a human-readable summary of the current branch's annotations.

### Usage

```bash
specmap status [flags]
```

### Flags

Inherits [global flags](overview.md#global-flags) only.

### Example Output

```
Branch: feature/add-auth (base: main)
Head SHA: a1b2c3d4

Annotations: 12 total across 5 files

  auth/session.go (3 annotations)
    :15-42  Implements JWT session token creation and validation with
            httpOnly cookie storage [1] and 24-hour expiry [2].
    :44-61  Handles token refresh middleware that silently renews
            expired tokens on each API request [1].
    :63-78  Session cleanup on explicit logout [1].

  auth/hash.go (2 annotations)
    :8-23   Bcrypt password hashing with cost factor 12 [1].
    :25-40  Password verification with constant-time comparison [1].

  ...

Coverage: 10/12 annotations have spec refs
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
| `--threshold` | `0.0` | Minimum coverage ratio (0.0-1.0). Exits 1 if below. |
| `--base` | From specmap file | Base branch for diff comparison |
| `--json` | `false` | Output JSON instead of human-readable text |

Plus [global flags](overview.md#global-flags).

### Human Output Example

```
specmap: checking coverage for feature/add-auth (base: main)
Files: 10/12 covered | Lines: 245/298 covered
Uncovered:
  auth/middleware.go (0%, 38 lines)
  hooks/useAuth.ts (0%, 15 lines)
Overall: 82.2% (threshold: 80.0%) -- PASS
```

### JSON Output

Use `--json` for machine-readable output (useful in CI scripts):

```json
{
  "branch": "feature/add-auth",
  "base_branch": "main",
  "total_files": 12,
  "covered_files": 10,
  "total_lines": 298,
  "covered_lines": 245,
  "coverage": 0.822,
  "threshold": 0.80,
  "pass": true,
  "uncovered": [
    {
      "file": "auth/middleware.go",
      "coverage": 0.0,
      "total_lines": 38,
      "covered_lines": 0
    }
  ]
}
```

### Exit Behavior

- Exits `0` if coverage >= threshold (or no threshold set)
- Exits `1` if coverage < threshold
- Both human and JSON modes respect the exit code
