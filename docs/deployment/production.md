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
                    │  GitHub API               │
                    │  OAuth + Contents API     │
                    └──────────────────────────┘
```

- **Single process**: `specmap serve` runs the API server with the React frontend embedded (when built with `--static-dir`)
- **SQLite**: all state (users, tokens, cached PR data) stored in a single file
- **No webhooks**: the server fetches data from GitHub on demand via the Contents API
- **TLS**: handled by a reverse proxy in front of the application

## GitHub OAuth App Setup

Go to [github.com/settings/developers](https://github.com/settings/developers) → **OAuth Apps** → **New OAuth App**:

| Field | Value |
|-------|-------|
| Application name | Specmap |
| Homepage URL | `https://your-domain.com` |
| Authorization callback URL | `https://your-domain.com/api/v1/auth/callback` |

Save the **Client ID** and generate a **Client Secret**.

No installation step is needed — OAuth Apps use the `repo` scope to access repositories the authenticated user has access to.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `PORT` | No | Port to listen on (default: `8080`) |
| `HOST` | No | Host to bind to (default: `0.0.0.0`) |
| `BASE_URL` | Yes | Public URL of the server (e.g., `https://specmap.example.com`) |
| `DATABASE_PATH` | No | Path to SQLite database file (default: `./specmap.db`) |
| `GITHUB_CLIENT_ID` | Yes | OAuth App Client ID |
| `GITHUB_CLIENT_SECRET` | Yes | OAuth App Client Secret |
| `SESSION_SECRET` | Yes | Random string, 32+ characters (`openssl rand -hex 32`) |
| `ENCRYPTION_KEY` | Yes | 32 bytes hex-encoded for AES-256-GCM token encryption (`openssl rand -hex 32`) |
| `CORS_ORIGIN` | No | Set only if frontend is served from a different origin |
| `FRONTEND_URL` | No | Where to redirect after OAuth login (defaults to `CORS_ORIGIN` or `BASE_URL`) |
| `STATIC_DIR` | No | Directory with built frontend files (for embedded SPA mode) |

### Example `.env`

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
  -e GITHUB_CLIENT_ID=Iv1.abc123 \
  -e GITHUB_CLIENT_SECRET=secret123 \
  -e SESSION_SECRET=$(openssl rand -hex 32) \
  -e ENCRYPTION_KEY=$(openssl rand -hex 32) \
  specmap:latest
```

The Docker image bundles the Python API server with the built React frontend. It runs `specmap serve --static-dir /app/static` to serve both from a single process.

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
