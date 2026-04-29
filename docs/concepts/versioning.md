# Versioning

Specmap uses a single version tracked in `pyproject.toml`. The Python package (core library, CLI, MCP server, API server) and the React frontend are versioned together and released as one wheel.

## Checking Versions

```bash
specmap --version          # specmap 0.4.0
```

## Bumping Versions

```bash
# Update pyproject.toml
just version 0.5.0

# Or release: bump, commit, tag, and push (triggers PyPI publish via GitHub Actions)
just release 0.5.0
```

The `just release` command updates `pyproject.toml`, commits the change, creates a `v{VERSION}` git tag, and pushes. The GitHub Actions workflow (`publish.yml`) builds the wheel (including the bundled frontend) and publishes to PyPI via trusted publishing.

## Git Tag Convention

Tags follow the format `v{major}.{minor}.{patch}` (e.g., `v0.4.0`).

Both follow [semantic versioning](https://semver.org/). During pre-1.0 development, minor bumps may include breaking changes.

## The Schema Contract

The specmap JSON schema (`version: 2`) is the interop contract between the annotation generator and consumers (CLI validation, web UI). It is an integer in the model definitions -- not a release version. When the schema version increments, the annotation generator and all consumers must be updated to support it.

## Frontend Bundling

The React frontend is built and bundled into the Python wheel during package installation via a Hatch custom build hook. Running `just build` or `uv build` produces a wheel that includes the compiled frontend in `specmap/_static/`. No separate frontend deployment is needed.

## Documentation Versions

Documentation versions (via [mike](https://github.com/jimporter/mike)) track releases:

```bash
just docs-deploy 0.4    # Deploy docs for v0.4
```
