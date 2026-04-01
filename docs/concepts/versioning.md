# Versioning

Specmap uses **two version groups** that release independently.

## Version Groups

| Group | Components | Source of truth | Git tag |
|-------|-----------|----------------|---------|
| **core** | Python library, CLI, MCP server | `core/pyproject.toml` | `core/v0.1.0` |
| **web** | Go API + React frontend | `api/VERSION` | `web/v0.1.0` |

### Why two groups?

The core tools (CLI, MCP server) are installed locally by developers and evolve based on annotation/validation needs. The web components (API server, frontend) are deployed together as a single service and evolve based on UI and collaboration features. Separating them allows each to release at its own cadence without unnecessary coupling.

### The schema contract

The specmap JSON schema (`version: 2`) is the interop contract between core and web. It is an integer in the model definitions — not a release version, and it does not get a git tag. When the schema version increments, both groups must be updated to support it.

## Checking Versions

```bash
# Core version
specmap --version          # specmap 0.1.0

# Web version (API health endpoint)
curl -s https://localhost:8080/healthz
# {"status":"ok","version":"0.1.0"}

# Both at once
just versions
```

## Bumping Versions

```bash
# Bump core (updates pyproject.toml)
just core-version 0.2.0
git tag core/v0.2.0

# Bump web (updates api/VERSION)
just web-version 0.2.0
git tag web/v0.2.0
```

The `just` commands update the source-of-truth file and print a reminder to create the git tag. Tags are manual — there is no automated release pipeline yet.

## Git Tag Convention

- **Core releases**: `core/v{major}.{minor}.{patch}` (e.g., `core/v0.1.0`)
- **Web releases**: `web/v{major}.{minor}.{patch}` (e.g., `web/v0.1.0`)

Both follow [semantic versioning](https://semver.org/). During pre-1.0 development, minor bumps may include breaking changes.

## Compatibility Matrix

| Core | Web | Schema |
|------|-----|--------|
| 0.1.x | 0.1.x | 2 |

Core and web are compatible as long as they agree on the schema version. The API server reads specmap JSON files produced by core — if the schema `version` field matches, they interoperate.

## Documentation Versions

Documentation versions (via [mike](https://github.com/jimporter/mike)) track **core** releases, since the docs primarily cover the CLI and MCP tools that developers install locally.

```bash
just docs-deploy 0.1    # Deploy docs for core v0.1
```
