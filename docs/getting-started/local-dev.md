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
| Go 1.25+ | API server | [go.dev/dl](https://go.dev/dl/) |
| Node.js 20+ | React frontend | System package manager |
| Docker | PostgreSQL | [docs.docker.com](https://docs.docker.com/get-docker/) |
| [just](https://github.com/casey/just) | Task runner | `cargo install just` or system package manager |
| [mkcert](https://github.com/FiloSottile/mkcert) | Local HTTPS certificates | `go install filippo.io/mkcert@latest` or system package manager |

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
OpenAI / Anthropic / etc.                Go API Server (:8080)
    │                                        │
    ▼                                        ▼
.specmap/{branch}.json ◄─── git ───►     GitHub Contents API
(committed to repo)                      (fetches .specmap/ at head SHA)
                                             │
                                             ▼
                                         PostgreSQL (cache)
```

**The link between them is git.** The MCP server writes `.specmap/{branch}.json` to the repo and the developer commits it. The web UI fetches that file from GitHub via the Contents API when a reviewer opens a PR.

## Part 1: Generate Annotations

This part doesn't need the web UI, Docker, or Go. It's the Phase 1 workflow, and it happens entirely in **your target project** (not in the specmap repo).

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

This requires the Go API server, PostgreSQL, and the React frontend.

### 1. Create a GitHub App

Go to [github.com/settings/apps/new](https://github.com/settings/apps/new):

| Field | Value |
|-------|-------|
| GitHub App name | Specmap (dev) |
| Homepage URL | `https://localhost:8080` |
| Callback URL | `https://localhost:8080/api/v1/auth/callback` |
| Request user authorization (OAuth) during installation | Checked |
| Webhook | **Uncheck "Active"** — not needed for local dev (see [Production Deployment](../deployment/production.md) for webhook setup) |

**Required permissions (under "Repository permissions"):**

| Permission | Access |
|------------|--------|
| Contents | Read-only |
| Pull requests | Read-only |
| Metadata | Read-only |

No account or organization permissions are needed.

**Where can this GitHub App be installed?**

- **Only on this account** — use this for local development
- **Any account** — select this if you want other users or organizations to install it; an org admin must approve the installation

Save the **Client ID** and generate a **Client Secret**.

After creating the App, install it on the repositories you want specmap to access. Go to your App settings > Install App, select your account, and choose "Only select repositories." For organizations, an org admin (or someone with GitHub App management permissions) must perform the installation.

### 2. Generate local HTTPS certificates

The session cookie is always `Secure: true` (no dev-mode toggle), so the API server must run over HTTPS locally. You need a TLS certificate and key for `localhost`.

#### Option A: mkcert (recommended)

[mkcert](https://github.com/FiloSottile/mkcert) creates locally-trusted certificates — your browser will show a green lock with no warnings.

**Install mkcert:**

=== "macOS"

    ```bash
    brew install mkcert
    ```

=== "Linux"

    ```bash
    # Debian/Ubuntu
    sudo apt install libnss3-tools
    go install filippo.io/mkcert@latest

    # Arch
    sudo pacman -S mkcert
    ```

=== "Windows"

    ```bash
    choco install mkcert
    ```

**Generate certificates:**

```bash
mkcert -install                    # Install local CA into system trust store (one time, needs sudo/admin)
mkcert localhost 127.0.0.1 ::1     # Generates localhost+1.pem and localhost+1-key.pem
```

`mkcert -install` creates a local certificate authority (CA) and adds it to your system's trust store and browsers' certificate databases. After this, any certificate signed by this CA is trusted automatically. The CA key is stored in `$(mkcert -CAROOT)`.

Move the generated `.pem` files to the specmap root (or anywhere — just update the paths in `.env`).

#### Option B: openssl (no extra tools)

If you don't want to install mkcert, `openssl` works but your browser will show a certificate warning that you'll need to click through.

```bash
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout localhost-key.pem -out localhost.pem \
  -days 365 -subj '/CN=localhost' \
  -addext 'subjectAltName=DNS:localhost,IP:127.0.0.1,IP:::1'
```

Then set `TLS_CERT=localhost.pem` and `TLS_KEY=localhost-key.pem` in `.env`.

!!! note
    With self-signed certs, Chrome will show "Your connection is not private." Click **Advanced > Proceed to localhost** to continue. You'll need to do this once per session. Firefox may require adding a permanent exception.

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```bash
DATABASE_URL=postgres://specmap:specmap_dev@localhost:5432/specmap?sslmode=disable
PORT=8080
BASE_URL=https://localhost:8080

GITHUB_CLIENT_ID=<from step 1>
GITHUB_CLIENT_SECRET=<from step 1>

SESSION_SECRET=$(openssl rand -hex 32)
ENCRYPTION_KEY=$(openssl rand -hex 32)

CORS_ORIGIN=http://localhost:5173

TLS_CERT=localhost+1.pem
TLS_KEY=localhost+1-key.pem
```

### 4. Start services

Three terminals:

```bash
# Terminal 1: PostgreSQL
just dev-up

# Terminal 2: Go API server
just api-run

# Terminal 3: React frontend
just web-install   # first time only
just web-dev
```

### 5. Log in

Open [http://localhost:5173](http://localhost:5173) in your browser. Click "Sign in with GitHub". This redirects through GitHub OAuth and back to the app.

### 6. Browse a PR

After login, the dashboard shows your GitHub repos. Click a repo, then click a PR that has a `.specmap/{branch}.json` file committed.

The PR review page shows:

- **Diff viewer** — each file's diff rendered with syntax highlighting
- **Annotation widgets** — blue cards inline in the diff showing annotation descriptions
- **`[N]` badges** — clickable citations in the annotation text; hover for a tooltip with the spec heading and excerpt
- **Spec panel** — clicking a badge opens a side panel showing the spec file's markdown content, scrolled to the cited section

If the PR has no `.specmap/` file, the annotations section is empty.

---

## What Docker Compose Covers

Docker Compose only runs PostgreSQL:

```yaml
services:
  postgres:
    image: postgres:16-alpine
    ports: ["5432:5432"]
    environment:
      POSTGRES_DB: specmap
      POSTGRES_USER: specmap
      POSTGRES_PASSWORD: specmap_dev
```

The Go API server and Vite dev server run directly on the host. The API server auto-runs migrations on startup.

**Not containerized:** the Go server, Vite, the MCP server, or the CLI. These run natively for fast iteration. A production Docker setup would bundle the Go binary + embedded React build into a single container.

---

## Troubleshooting

**"Secure cookie not being set"** — You're hitting the API over HTTP instead of HTTPS. Make sure `TLS_CERT` and `TLS_KEY` are set and the Go server logs `server starting (TLS)`.

**"CORS error in browser console"** — Check that `CORS_ORIGIN` in `.env` matches the Vite dev server URL exactly (`http://localhost:5173`).

**"Empty annotations on PR page"** — The `.specmap/{branch}.json` file must be committed and pushed to the PR branch. The API fetches it from GitHub at the PR's head SHA.

**"OAuth callback error"** — Verify the callback URL in your GitHub App settings matches `BASE_URL` + `/api/v1/auth/callback` exactly.

**"No repositories found"** — The GitHub App must be installed on at least one repository. Go to your GitHub App settings > Install App and select the repositories you want specmap to access.

**"Login redirects but no session"** — Check that `BASE_URL` uses `https://` (not `http://`). The session cookie requires a secure context.
