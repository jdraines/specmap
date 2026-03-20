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

Annotations: 10/12 have spec refs
```
