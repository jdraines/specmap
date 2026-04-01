# Production Deployment

This guide covers deploying specmap for general use — where arbitrary users and organizations install the GitHub App and the server runs on a public URL.

## Architecture

Production specmap operates in two modes simultaneously:

```
Pull-based (user requests)              Push-based (webhooks)
──────────────────────────              ──────────────────────
Browser                                 GitHub
    │                                       │
    ▼                                       ▼
Vite / Static Build                     POST /api/v1/webhooks/github
    │                                       │ HMAC verification
    ▼                                       ▼
Go API Server ◄──── OAuth (user) ────►  Go API Server ◄──── App JWT ────► GitHub API
    │                                       │
    ▼                                       ▼
PostgreSQL                              PostgreSQL
```

- **Pull-based**: Users log in via OAuth, browse repos and PRs. The server uses their OAuth token to call GitHub APIs on their behalf.
- **Push-based**: GitHub sends webhook events when users install/uninstall the App or change repo access. The server verifies the HMAC signature and updates its installation records.

## GitHub App Setup

### Differences from Local Dev

| Setting | Local Dev | Production |
|---------|-----------|------------|
| Who can install | Only on this account | **Any account** |
| Webhook | Inactive | **Active** — pointed at your server |
| Webhook secret | Not set | **Required** — HMAC verification |
| Private key | Not needed | **Required** — for App-level API calls |

### Creating the App

Go to [github.com/settings/apps/new](https://github.com/settings/apps/new):

| Field | Value |
|-------|-------|
| GitHub App name | Specmap |
| Homepage URL | Your production URL |
| Callback URL | `https://your-domain.com/api/v1/auth/callback` |
| Setup URL (optional) | `https://your-domain.com` (where users land after installing) |
| Request user authorization (OAuth) during installation | Checked |
| Webhook URL | `https://your-domain.com/api/v1/webhooks/github` |
| Webhook secret | A random string (save this for `GITHUB_WEBHOOK_SECRET`) |
| Webhook Active | Checked |

### Permissions

Same as local dev — all read-only:

| Permission | Access |
|------------|--------|
| Contents | Read-only |
| Pull requests | Read-only |
| Metadata | Read-only |

### Webhook Event Subscriptions

Subscribe to these events:

| Event | Purpose |
|-------|---------|
| `Installation` | Track when users install/uninstall the App |
| `Installation repositories` | Track when users change repo access |

### Private Key

After creating the App, generate a private key:

1. Go to your App settings > General > Private keys
2. Click "Generate a private key"
3. Save the downloaded `.pem` file securely on your server

### Where Can This App Be Installed?

Select **Any account** so that other users and organizations can install it. An org admin must approve the installation for organization accounts.

## Environment Variables

All environment variables from [local dev](../getting-started/local-dev.md) apply, plus these three for production features:

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_APP_ID` | For app auth | The App ID from your GitHub App settings page |
| `GITHUB_PRIVATE_KEY_PATH` | For app auth | Path to the `.pem` private key file |
| `GITHUB_WEBHOOK_SECRET` | For webhooks | The secret you set in the GitHub App webhook configuration |

App-level authentication activates when both `GITHUB_APP_ID` and `GITHUB_PRIVATE_KEY_PATH` are set. The webhook endpoint activates when `GITHUB_WEBHOOK_SECRET` is set. Both are independent — you can enable one without the other.

### Example `.env`

```bash
# Server
PORT=8080
BASE_URL=https://specmap.example.com

# Database
DATABASE_URL=postgres://specmap:$PASSWORD@db-host:5432/specmap?sslmode=require

# GitHub OAuth
GITHUB_CLIENT_ID=Iv1.abc123
GITHUB_CLIENT_SECRET=secret123

# Session & encryption
SESSION_SECRET=$(openssl rand -hex 32)
ENCRYPTION_KEY=$(openssl rand -hex 32)

# GitHub App (production)
GITHUB_APP_ID=12345
GITHUB_PRIVATE_KEY_PATH=/etc/specmap/private-key.pem
GITHUB_WEBHOOK_SECRET=$(openssl rand -hex 32)

# CORS (set to your frontend URL, or omit if serving from same origin)
CORS_ORIGIN=https://specmap.example.com

# TLS (if terminating TLS at the app level; omit if behind a reverse proxy)
# TLS_CERT=/etc/specmap/cert.pem
# TLS_KEY=/etc/specmap/key.pem
```

## Installation Flow for End Users

When someone clicks "Install" on the GitHub App page:

1. GitHub shows the installation consent screen listing requested permissions
2. The user selects "All repositories" or specific repos, then clicks Install
3. GitHub sends an `installation` webhook event (`action: created`) to your server
4. The server upserts an installation record in the database
5. If "Request user authorization during installation" is checked, GitHub redirects the user through the OAuth flow, landing them on your Setup URL

## Local Dev Compatibility

All production features are opt-in. When `GITHUB_APP_ID`, `GITHUB_PRIVATE_KEY_PATH`, and `GITHUB_WEBHOOK_SECRET` are not set:

- No App-level authentication is configured (`appAuth` is nil)
- The webhook endpoint is not registered (returns 404)
- Everything else works exactly as in local dev
