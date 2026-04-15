CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    provider_id INTEGER NOT NULL,
    login TEXT NOT NULL,
    name TEXT DEFAULT '',
    avatar_url TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE(provider, provider_id)
);

CREATE TABLE IF NOT EXISTS user_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    access_token_encrypted BLOB NOT NULL,
    token_type TEXT DEFAULT 'bearer',
    scope TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS repositories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    provider_id INTEGER NOT NULL,
    owner TEXT NOT NULL,
    name TEXT NOT NULL,
    full_name TEXT NOT NULL,
    private INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE(provider, provider_id)
);

CREATE TABLE IF NOT EXISTS pull_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    number INTEGER NOT NULL,
    title TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'open',
    head_branch TEXT NOT NULL,
    base_branch TEXT NOT NULL,
    head_sha TEXT NOT NULL,
    author_login TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE(repository_id, number)
);

CREATE TABLE IF NOT EXISTS mapping_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pull_request_id INTEGER NOT NULL REFERENCES pull_requests(id) ON DELETE CASCADE,
    head_sha TEXT NOT NULL,
    specmap_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE(pull_request_id, head_sha)
);

CREATE TABLE IF NOT EXISTS walkthrough_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pull_request_id INTEGER NOT NULL REFERENCES pull_requests(id) ON DELETE CASCADE,
    head_sha TEXT NOT NULL,
    familiarity INTEGER NOT NULL,
    depth TEXT NOT NULL,
    walkthrough_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE(pull_request_id, head_sha, familiarity, depth)
);

CREATE INDEX IF NOT EXISTS idx_pull_requests_repo_state ON pull_requests(repository_id, state);
CREATE INDEX IF NOT EXISTS idx_mapping_cache_pr_sha ON mapping_cache(pull_request_id, head_sha);
CREATE INDEX IF NOT EXISTS idx_walkthrough_cache_key
    ON walkthrough_cache(pull_request_id, head_sha, familiarity, depth);
