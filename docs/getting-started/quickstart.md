# Quick Start

This walkthrough takes you from zero to a validated spec-to-code mapping in five steps.

## Step 1: Write a Spec

Create a markdown spec file in your repo. Specmap auto-discovers `**/*.md` files (excluding `README.md`, `CHANGELOG.md`, and similar).

```markdown
# Authentication

## Token Storage

Sessions use signed JWTs stored in httpOnly cookies.
Tokens expire after 24 hours and are refreshed silently
on each API request.

## Password Hashing

All passwords are hashed with bcrypt (cost factor 12)
before storage. Plain-text passwords are never persisted.
```

## Step 2: Set Your API Key

Specmap needs an LLM to understand the semantic relationship between specs and code. Set your API key:

```bash
export SPECMAP_API_KEY="sk-..."
```

By default, Specmap uses `gpt-4o-mini`. See [Configuration](configuration.md) to use a different model or provider.

## Step 3: Code with Your Agent

Start coding with your MCP-connected agent. As it writes code, it calls `specmap_map` automatically to create mappings between your spec and the code changes.

Example: the agent implements the token storage described in your spec. Behind the scenes, the MCP server:

1. Parses the spec into sections with content hashes
2. Analyzes the code diff against the base branch
3. Asks the LLM which spec spans describe the intent behind each code change
4. Writes mappings to `.specmap/{branch}.json`

## Step 4: Check Status

Review what's been mapped:

```bash
specmap status
```

```
Spec Documents:
  docs/auth.md (2 sections)

Mappings: 3 total, 3 valid, 0 stale
  auth/session.go:15-42 → auth.md > Authentication > Token Storage
  auth/session.go:44-61 → auth.md > Authentication > Token Storage
  auth/hash.go:8-23     → auth.md > Authentication > Password Hashing
```

Validate that all hashes are intact:

```bash
specmap validate
```

```
✓ auth.md doc_hash valid
✓ auth/session.go:15-42 content_hash valid
✓ auth/session.go:44-61 content_hash valid
✓ auth/hash.go:8-23 content_hash valid

Validation: 4/4 passed
```

## Step 5: Enforce in CI

Add a coverage check to your CI pipeline:

```bash
specmap check --threshold 0.80
```

```
specmap: checking coverage for feature/add-auth (base: main)
Files: 2/2 mapped | Lines: 65/65 mapped
Overall: 100.0% (threshold: 80.0%) — PASS
```

If coverage drops below the threshold, the command exits with code 1, failing your CI check. See [CI Integration](../cli/ci.md) for a full GitHub Actions example.
