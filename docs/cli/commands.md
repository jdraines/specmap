# Commands Reference

## serve

Starts the specmap API server with the embedded React frontend. Auto-opens a browser when a frontend is available.

### Usage

```bash
specmap serve [flags]
```

### Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--port` | `8080` | Port to listen on |
| `--host` | `127.0.0.1` | Host to bind to |
| `--db` | `./specmap.db` | SQLite database path |
| `--static-dir` | *(auto)* | Directory with built frontend files (overrides bundled frontend) |
| `--reload` | `false` | Enable auto-reload for development |
| `--no-open` | `false` | Don't auto-open the browser |

### Static File Resolution

The frontend is resolved in this order:

1. `--static-dir` flag (explicit path)
2. `STATIC_DIR` environment variable
3. Bundled `_static/` directory (included in the pip package)

If none are found, the server runs as an API-only backend (no browser auto-open).

### Examples

```bash
# Typical local use — browser opens automatically
specmap serve

# Suppress browser auto-open
specmap serve --no-open

# Bind to all interfaces (Docker / remote access)
specmap serve --host 0.0.0.0

# Development with auto-reload
specmap serve --reload --no-open

# Use a custom frontend build
specmap serve --static-dir ../web/dist
```

---

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
