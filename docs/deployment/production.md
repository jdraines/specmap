# Production Deployment

This guide covers self-hosting specmap for your team — a single process serving the API and frontend, backed by SQLite.

## Architecture

```
                    ┌──────────────────────────┐
Browser ──────────► │  Reverse Proxy           │
                    │  (nginx / caddy)         │
                    │  TLS termination         │
                    └────────────┬─────────────┘
                                 │ HTTP
                    ┌────────────▼─────────────┐
                    │  specmap serve            │
                    │  Python (FastAPI/Uvicorn) │
                    │  Embedded React SPA       │
                    │  SQLite (specmap.db)      │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │  Forge API               │
                    │  GitHub / GitLab         │
                    │  (auto-detected)         │
                    └──────────────────────────┘
```

- **Single process**: `specmap serve` runs the API server with the React frontend embedded (when built with `--static-dir`)
- **SQLite**: all state (users, tokens, cached PR data) stored in a single file
- **No webhooks**: the server fetches data from the forge on demand via the API
- **Auto-detection**: forge provider (GitHub or GitLab) is detected from `git remote origin`
- **TLS**: handled by a reverse proxy in front of the application

## Auth Configuration

Specmap supports two auth modes. Choose the one that fits your environment.

### PAT mode (recommended for most teams)

Set a personal access token as an environment variable. The server authenticates on startup — no login page needed.

**GitHub:**

```bash
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
```

Or ensure `gh` CLI is authenticated on the server (`gh auth login`).

**GitLab:**

```bash
GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx
```

Or ensure `glab` CLI is authenticated on the server.

### OAuth mode (enterprise)

For organizations that restrict PATs, configure OAuth credentials instead.

**GitHub** — go to [github.com/settings/developers](https://github.com/settings/developers) > **OAuth Apps** > **New OAuth App**:

| Field | Value |
|-------|-------|
| Application name | Specmap |
| Homepage URL | `https://your-domain.com` |
| Authorization callback URL | `https://your-domain.com/api/v1/auth/callback/github` |

**GitLab** — go to your GitLab instance > **Admin** > **Applications** > **New Application**:

| Field | Value |
|-------|-------|
| Name | Specmap |
| Redirect URI | `https://your-domain.com/api/v1/auth/callback/gitlab` |
| Scopes | `read_api`, `read_repository` |

Set the client credentials:

```bash
GITHUB_CLIENT_ID=Iv1.abc123
GITHUB_CLIENT_SECRET=secret123
# or for GitLab:
GITLAB_CLIENT_ID=app_id_123
GITLAB_CLIENT_SECRET=secret123
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `PORT` | No | Port to listen on (default: `8080`) |
| `HOST` | No | Host to bind to (default: `0.0.0.0`) |
| `BASE_URL` | Yes | Public URL of the server (e.g., `https://specmap.example.com`) |
| `DATABASE_PATH` | No | Path to SQLite database file (default: `./specmap.db`) |
| `GITHUB_TOKEN` | * | GitHub PAT (PAT mode) |
| `GITLAB_TOKEN` | * | GitLab PAT (PAT mode) |
| `GITHUB_CLIENT_ID` | * | GitHub OAuth App Client ID (OAuth mode) |
| `GITHUB_CLIENT_SECRET` | * | GitHub OAuth App Client Secret (OAuth mode) |
| `GITLAB_CLIENT_ID` | * | GitLab OAuth App ID (OAuth mode) |
| `GITLAB_CLIENT_SECRET` | * | GitLab OAuth App Secret (OAuth mode) |
| `SESSION_SECRET` | No | Random string, 32+ chars (auto-generated if not set) |
| `ENCRYPTION_KEY` | No | 32 bytes hex-encoded for AES-256-GCM (auto-generated if not set) |
| `SPECMAP_FORGE` | No | Force forge provider: `github` or `gitlab` (auto-detected from git remote) |
| `SPECMAP_FORGE_URL` | No | Base URL for self-hosted GitLab (e.g., `https://gitlab.example.com`) |
| `CORS_ORIGIN` | No | Set only if frontend is served from a different origin |
| `FRONTEND_URL` | No | Where to redirect after OAuth login (defaults to `CORS_ORIGIN` or `BASE_URL`) |
| `STATIC_DIR` | No | Directory with built frontend files (for embedded SPA mode) |

\* At least one auth method must be configured for the detected provider.

### Example `.env` (PAT mode)

```bash
PORT=8080
BASE_URL=https://specmap.example.com
DATABASE_PATH=/data/specmap.db
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
```

### Example `.env` (OAuth mode)

```bash
PORT=8080
BASE_URL=https://specmap.example.com
DATABASE_PATH=/data/specmap.db
GITHUB_CLIENT_ID=Iv1.abc123
GITHUB_CLIENT_SECRET=secret123
SESSION_SECRET=$(openssl rand -hex 32)
ENCRYPTION_KEY=$(openssl rand -hex 32)
```

## Docker Deployment

Build and run with Docker:

```bash
docker build -t specmap:latest .

docker run -d \
  --name specmap \
  -p 8080:8080 \
  -v specmap-data:/data \
  -e BASE_URL=https://specmap.example.com \
  -e DATABASE_PATH=/data/specmap.db \
  -e GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx \
  specmap:latest
```

The Docker image bundles the Python API server with the built React frontend. It runs `specmap serve --static-dir /app/static` to serve both from a single process.

### Self-hosted GitLab

```bash
docker run -d \
  --name specmap \
  -p 8080:8080 \
  -v specmap-data:/data \
  -e BASE_URL=https://specmap.example.com \
  -e DATABASE_PATH=/data/specmap.db \
  -e GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx \
  -e SPECMAP_FORGE=gitlab \
  -e SPECMAP_FORGE_URL=https://gitlab.example.com \
  specmap:latest
```

## Reverse Proxy

Put a reverse proxy in front for TLS termination. Example with Caddy:

```
specmap.example.com {
    reverse_proxy localhost:8080
}
```

Example with nginx:

```nginx
server {
    listen 443 ssl;
    server_name specmap.example.com;

    ssl_certificate /etc/letsencrypt/live/specmap.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/specmap.example.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

When `BASE_URL` starts with `https://`, the server sets `Secure` on session cookies, so TLS termination at the proxy is required.

## SQLite Considerations

- **Single-writer**: SQLite uses a single-writer model. This is fine for typical specmap workloads (read-heavy, writes are infrequent token/cache upserts).
- **WAL mode**: The server enables WAL mode for better concurrent read performance.
- **Backup**: Copy the `.db` file (and `.db-wal`, `.db-shm` if they exist) while the server is running, or stop the server first for a clean copy.
- **Scaling**: For most teams, a single SQLite database is sufficient. If you need horizontal scaling, consider putting a shared filesystem or switching to PostgreSQL (not currently supported out of the box).

## Without Docker

You can also run specmap directly:

```bash
# Install
uv tool install git+https://github.com/jdraines/specmap.git#subdirectory=core

# Build frontend
cd web && npm ci && npm run build && cd ..

# Run with embedded frontend
specmap serve --static-dir web/dist
```
