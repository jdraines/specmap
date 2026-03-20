# Quick Start

This walkthrough takes you from zero to a validated spec-annotated codebase in five steps.

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

Specmap needs an LLM to generate annotations that link your code to spec intent. Set your API key:

```bash
export SPECMAP_API_KEY="sk-..."
```

By default, Specmap uses `gpt-4o-mini`. See [Configuration](configuration.md) to use a different model or provider.

## Step 3: Code with Your Agent

Start coding with your MCP-connected agent. As it writes code, it calls `specmap_annotate` automatically to create annotations linking your code changes to spec requirements.

Example: the agent implements the token storage described in your spec. Behind the scenes, the MCP server:

1. Runs `git diff` to find changed code
2. Reads the spec files in the repo
3. Sends the diff and specs to the LLM, which generates annotations with `[N]` spec citations
4. Writes annotations to `.specmap/{branch}.json`

## Step 4: Check Status

Review what's been annotated:

```bash
specmap status
```

```
Branch: feature/add-auth (base: main)
Head SHA: a1b2c3d4

Annotations: 3 total across 2 files

  auth/session.go (2 annotations)
    :15-42  Implements JWT session token creation with httpOnly
            cookie storage [1] and 24-hour expiry [2].
    :44-61  Handles silent token refresh on API requests [1].

  auth/hash.go (1 annotation)
    :8-23   Bcrypt password hashing with cost factor 12 [1].
```

Validate that all line ranges are still valid:

```bash
specmap validate
```

```
[ok] auth/session.go:15-42 valid
[ok] auth/session.go:44-61 valid
[ok] auth/hash.go:8-23 valid

Validation: 3/3 passed
```

## Step 5: Enforce in CI

Add a coverage check to your CI pipeline:

```bash
specmap check --threshold 0.80
```

```
specmap: checking coverage for feature/add-auth (base: main)
Files: 2/2 covered | Lines: 65/65 covered
Overall: 100.0% (threshold: 80.0%) -- PASS
```

If coverage drops below the threshold, the command exits with code 1, failing your CI check. See [CI Integration](../cli/ci.md) for a full GitHub Actions example.
