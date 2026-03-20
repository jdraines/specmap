# Manual E2E Test Guide

Verify the full specmap annotation flow end-to-end: MCP server generates annotations with an LLM, and the CLI validates them.

## Prerequisites

- Python 3.11+, `uv` installed
- A working LLM API key (OpenAI, Anthropic, or any litellm-supported provider)
- A git repository with at least one markdown spec file and some code changes on a feature branch

## 1. Install Dependencies

```bash
cd core
uv sync
```

## 2. Configure Your LLM

Set your API key and optionally choose a model:

```bash
# OpenAI (default model: gpt-4o-mini)
export SPECMAP_API_KEY="sk-..."

# Or use Anthropic Claude
export SPECMAP_MODEL="claude-sonnet-4-20250514"
export SPECMAP_API_KEY="sk-ant-..."
```

You can also write `.specmap/config.json` in the repo root (make sure it's gitignored):

```json
{
  "model": "claude-sonnet-4-20250514",
  "api_key": "sk-ant-..."
}
```

## 3. Set Up a Test Repo

Either use an existing repo with a feature branch, or create a throwaway one:

```bash
mkdir /tmp/specmap-e2e && cd /tmp/specmap-e2e
git init && git config user.email "test@test.com" && git config user.name "Test"

# Create a spec on main
mkdir docs
cat > docs/auth-spec.md << 'EOF'
# Authentication

## Token Storage

Sessions use signed JWTs stored in httpOnly cookies.
Tokens expire after 24 hours and are refreshed silently
on each API request.

## Password Hashing

All passwords are hashed with bcrypt (cost factor 12)
before storage. Plain-text passwords are never persisted.
EOF

git add . && git commit -m "Add auth spec"
git branch -M main

# Create a feature branch with code
git checkout -b feature/add-auth

cat > session.go << 'EOF'
package auth

import (
    "net/http"
    "time"
)

const tokenExpiry = 24 * time.Hour

// CreateSession issues a signed JWT and sets it as an httpOnly cookie.
func CreateSession(w http.ResponseWriter, userID string) error {
    token, err := signJWT(userID, tokenExpiry)
    if err != nil {
        return err
    }
    http.SetCookie(w, &http.Cookie{
        Name:     "session",
        Value:    token,
        HttpOnly: true,
        Secure:   true,
        MaxAge:   int(tokenExpiry.Seconds()),
    })
    return nil
}
EOF

git add . && git commit -m "Implement session token creation"
```

## 4. Test the MCP Server Directly

The MCP server runs over stdio, but the easiest way to test is to call the tool functions directly from Python:

```bash
cd /path/to/specmap/core
uv run python -c "
import asyncio
from specmap.tools.annotate import annotate

async def main():
    result = await annotate(
        repo_root='/tmp/specmap-e2e',
        branch='feature/add-auth',
    )
    import json
    print(json.dumps(result, indent=2, default=str))

asyncio.run(main())
"
```

**What to verify:**
- `status` is `"ok"`
- `annotations_created` is >= 1
- `total_annotations` matches `annotations_created`
- `llm_usage.total_calls` is >= 1 (confirms LLM was actually called)

## 5. Inspect the Generated Annotations

```bash
cat /tmp/specmap-e2e/.specmap/feature--add-auth.json | python -m json.tool
```

**What to verify in the JSON:**
- `version` is `2`
- `head_sha` is a non-empty git SHA
- `annotations` array has entries with:
  - `file` matching your code file (e.g. `session.go`)
  - `start_line` and `end_line` that make sense for the code
  - `description` is a natural-language sentence with `[1]`, `[2]`, etc. references
  - `refs` array with entries containing `spec_file`, `heading`, `start_line`, and `excerpt`

Example expected structure:

```json
{
  "annotations": [
    {
      "id": "a_...",
      "file": "session.go",
      "start_line": 1,
      "end_line": 25,
      "description": "Implements JWT session creation with 24h expiry and httpOnly cookie storage. [1]",
      "refs": [
        {
          "id": 1,
          "spec_file": "docs/auth-spec.md",
          "heading": "Token Storage",
          "start_line": 5,
          "excerpt": "Sessions use signed JWTs stored in httpOnly cookies. Tokens expire after 24 hours..."
        }
      ]
    }
  ]
}
```

## 6. Run CLI Validation

```bash
cd /tmp/specmap-e2e
uv run --project /path/to/specmap/core specmap --repo-root . --branch feature/add-auth validate
```

**Expected:** All annotations show "line range OK", exit code 0.

## 7. Run CLI Status

```bash
uv run --project /path/to/specmap/core specmap --repo-root . --branch feature/add-auth status
```

**Expected:** Shows annotation descriptions grouped by file, with line ranges and ref counts.

## 8. Test check_sync

```bash
uv run --project /path/to/specmap/core python -c "
import asyncio
from specmap.tools.check_sync import check_sync

async def main():
    result = await check_sync('/tmp/specmap-e2e', branch='feature/add-auth')
    print(result)

asyncio.run(main())
"
```

**Expected:** `valid` >= 1, `invalid` == 0.

## 9. Test Incremental Mode (Diff-Based Skip)

Add a second commit and re-annotate. The system should use `head_sha` to do an incremental diff:

```bash
cd /tmp/specmap-e2e

cat > hash.go << 'EOF'
package auth

import "golang.org/x/crypto/bcrypt"

const bcryptCost = 12

// HashPassword hashes a password with bcrypt.
func HashPassword(password string) (string, error) {
    bytes, err := bcrypt.GenerateFromPassword([]byte(password), bcryptCost)
    return string(bytes), err
}
EOF

git add hash.go && git commit -m "Add password hashing"
```

Now re-run annotate:

```bash
cd /path/to/specmap/core
uv run python -c "
import asyncio
from specmap.tools.annotate import annotate

async def main():
    result = await annotate(
        repo_root='/tmp/specmap-e2e',
        branch='feature/add-auth',
    )
    import json
    print(json.dumps(result, indent=2, default=str))

asyncio.run(main())
"
```

**What to verify:**
- `incremental` is `true` in the result (confirms diff-based skip was used)
- `annotations_kept` > 0 (the session.go annotation was preserved)
- New annotations were created for `hash.go`
- Total annotations increased

## 10. Test with MCP-Connected Agent (Optional)

If you use Claude Code or another MCP-connected agent, add the server to your configuration:

```json
{
  "mcpServers": {
    "specmap": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/specmap/core", "python", "-m", "specmap.mcp"],
      "env": {
        "SPECMAP_API_KEY": "sk-...",
        "SPECMAP_MODEL": "gpt-4o-mini"
      }
    }
  }
}
```

Then ask the agent to call `specmap_annotate` after making code changes. Verify the `.specmap/` file is created and the agent can read the tool response.

## Pass/Fail Checklist

| # | Check | Pass? |
|---|-------|-------|
| 1 | `annotate()` returns `status: "ok"` with `annotations_created >= 1` | |
| 2 | `.specmap/{branch}.json` has `version: 2` and non-empty `head_sha` | |
| 3 | Annotations have `description` with `[N]` references and matching `refs` entries | |
| 4 | `specmap validate` exits 0, all line ranges valid | |
| 5 | `specmap status` shows annotation descriptions grouped by file | |
| 6 | `check_sync()` returns `valid >= 1, invalid == 0` | |
| 7 | Second `annotate()` run shows `incremental: true` and preserves existing annotations | |
| 8 | (Optional) MCP agent can call `specmap_annotate` and receives JSON response | |
