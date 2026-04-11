# Local Development Walkthrough

This guide walks through a complete local workflow: generating specmap annotations on a project, then inspecting them through the web UI.

## What You Need

**For Part 1 (generate annotations) — just these:**

| Component | Purpose | Install |
|-----------|---------|---------|
| Python 3.11+ | MCP server, CLI | System package manager |
| [uv](https://docs.astral.sh/uv/) | Python package manager | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| An LLM API key | Annotation generation | OpenAI, Anthropic, or any litellm-supported provider |

**For Part 2 (web UI) — also need these, and a clone of the specmap repo:**

| Component | Purpose | Install |
|-----------|---------|---------|
| Node.js 20+ | React frontend | System package manager |
| [just](https://github.com/casey/just) | Task runner | `cargo install just` or system package manager |

## Architecture

There are two independent pieces that connect through git:

```
Phase 1 (local, generates data)          Phase 2 (web, displays data)
─────────────────────────────────        ──────────────────────────────
Coding Agent                             Browser (:5173)
    │ MCP stdio                              │
    ▼                                        ▼
Specmap MCP Server (Python)              Vite Dev Server
    │ LLM calls                              │ proxy /api
    ▼                                        ▼
OpenAI / Anthropic / etc.                Python API Server (:8080)
    │                                        │
    ▼                                        ▼
.specmap/{branch}.json ◄─── git ───►     GitHub Contents API
(committed to repo)                      (fetches .specmap/ at head SHA)
                                             │
                                             ▼
                                         SQLite (cache)
```

**The link between them is git.** The MCP server writes `.specmap/{branch}.json` to the repo and the developer commits it. The web UI fetches that file from GitHub via the Contents API when a reviewer opens a PR.

## Part 1: Generate Annotations

This part doesn't need the web UI or the specmap repo. It's the Phase 1 workflow, and it happens entirely in **your target project**.

### 1. Install specmap

```bash
uv tool install git+https://github.com/jdraines/specmap.git#subdirectory=core
```

This gives you two commands available globally: `specmap` (CLI) and `specmap-mcp` (MCP server).

### 2. Add the MCP server to your coding agent

In the **target project**, create `.mcp.json`:

```json
{
  "mcpServers": {
    "specmap": {
      "command": "specmap-mcp",
      "env": {
        "SPECMAP_API_KEY": "sk-..."
      }
    }
  }
}
```

Set `SPECMAP_MODEL` if you want something other than the default `gpt-4o-mini` (see [Configuration](configuration.md)).

### 3. Code on a feature branch

The target project needs:

- At least one markdown spec file (auto-discovered from `**/*.md`)
- Code changes on a feature branch (relative to `main`)

When your coding agent makes changes, it calls `specmap_annotate`. This generates `.specmap/{branch}.json` containing annotations with `[N]` spec citations. The file is written to the working tree — commit it with your code.

### 4. Verify locally

```bash
# From the target project directory
specmap status
specmap validate
```

### 5. Push

```bash
git add .specmap/
git commit -m "Add specmap annotations"
git push origin feature/my-branch
```

Open a pull request on GitHub. The `.specmap/{branch}.json` file is now in the PR.

---

## Part 2: View Annotations in the Web UI

This requires the Python API server and the React frontend.

### 1. Create a GitHub OAuth App

Go to [github.com/settings/developers](https://github.com/settings/developers) → **OAuth Apps** → **New OAuth App**:

| Field | Value |
|-------|-------|
| Application name | Specmap (dev) |
| Homepage URL | `http://localhost:8080` |
| Authorization callback URL | `http://localhost:8080/api/v1/auth/callback` |

Save the **Client ID** and generate a **Client Secret**.

No installation step is needed — OAuth Apps use the `repo` scope to access repositories the authenticated user has access to.

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```bash
PORT=8080
BASE_URL=http://localhost:8080

DATABASE_PATH=./specmap.db

GITHUB_CLIENT_ID=<from step 1>
GITHUB_CLIENT_SECRET=<from step 1>

SESSION_SECRET=$(openssl rand -hex 32)
ENCRYPTION_KEY=$(openssl rand -hex 32)

CORS_ORIGIN=http://localhost:5173
```

### 3. Start services

Two terminals:

```bash
# Terminal 1: Python API server
just serve         # or: just serve-dev (auto-reload)

# Terminal 2: React frontend
just web-install   # first time only
just web-dev
```

### 4. Log in

Open [http://localhost:5173](http://localhost:5173) in your browser. Click "Sign in with GitHub". This redirects through GitHub OAuth and back to the app.

### 5. Browse a PR

After login, the dashboard shows your GitHub repos. Click a repo, then click a PR that has a `.specmap/{branch}.json` file committed.

The PR review page shows:

- **Diff viewer** — each file's diff rendered with syntax highlighting
- **Layout modes** — toggle between inline, side-by-side, and auto layout in the toolbar; auto mode switches to inline below 1400px viewport width
- **Annotation widgets** — blue cards inline in the diff showing annotation descriptions
- **Hover cross-highlighting** — hovering an annotation highlights its corresponding code lines, and vice versa
- **`[N]` badges** — clickable citations in the annotation text; hover for a tooltip with the spec heading and excerpt
- **Spec panel** — clicking a badge opens a side panel showing the spec file's markdown content, scrolled to the cited section
- **Annotation minimap** — colored dots along the right edge of the viewport for jumping directly to annotations
- **File jumper** — dropdown in the toolbar to jump to a specific file in the diff
- **Hunk expansion** — click the expansion button between hunks to reveal hidden context lines (fetched from the file-source API)
- **Keyboard shortcuts** — press `?` to open the shortcut help overlay. Key bindings include: `j`/`k` (next/previous file), `n`/`p` (next/previous annotation), `o` (collapse/expand file), `t` (toggle theme), `Esc` (close panels)

If the PR has no `.specmap/` file, the annotations section is empty.

---

## Troubleshooting

**"CORS error in browser console"** — Check that `CORS_ORIGIN` in `.env` matches the Vite dev server URL exactly (`http://localhost:5173`).

**"Empty annotations on PR page"** — The `.specmap/{branch}.json` file must be committed and pushed to the PR branch. The API fetches it from GitHub at the PR's head SHA.

**"OAuth callback error"** — Verify the callback URL in your GitHub OAuth App settings matches `BASE_URL` + `/api/v1/auth/callback` exactly.
