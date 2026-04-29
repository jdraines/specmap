# Local Development Walkthrough

!!! note "This page has moved"
    The content from this guide has been reorganized:

    - **Using the web UI** (browsing PRs, annotations, walkthroughs, code review): see [Web UI Overview](../web-ui/overview.md)
    - **Generating annotations** (MCP, CLI, or web UI): see [Quick Start](quickstart.md)
    - **Developing specmap itself** (cloning the repo, running tests): see [Development](../development.md)

## Quick Reference

**To use specmap on your projects** (no clone needed):

```bash
pip install specmap
specmap serve           # Launch the web UI
```

**To develop specmap itself**:

```bash
git clone https://github.com/jdraines/specmap.git
cd specmap
just install            # Python deps
just web-install        # Node deps
just dev                # API server + Vite dev server
```

See the linked pages above for full details.
