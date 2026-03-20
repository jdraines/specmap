-- Initial schema for specmap API (Phase 2).

CREATE TABLE users (
    id          BIGSERIAL PRIMARY KEY,
    github_id   BIGINT    NOT NULL UNIQUE,
    login       TEXT      NOT NULL,
    name        TEXT      NOT NULL DEFAULT '',
    avatar_url  TEXT      NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE user_tokens (
    id                     BIGSERIAL PRIMARY KEY,
    user_id                BIGINT    NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    access_token_encrypted BYTEA     NOT NULL,  -- AES-256-GCM ciphertext
    token_type             TEXT      NOT NULL DEFAULT 'bearer',
    scope                  TEXT      NOT NULL DEFAULT '',
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id)
);

CREATE TABLE repositories (
    id          BIGSERIAL PRIMARY KEY,
    github_id   BIGINT    NOT NULL UNIQUE,
    owner       TEXT      NOT NULL,
    name        TEXT      NOT NULL,
    full_name   TEXT      NOT NULL,
    private     BOOLEAN   NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE pull_requests (
    id              BIGSERIAL PRIMARY KEY,
    repository_id   BIGINT    NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    number          INT       NOT NULL,
    title           TEXT      NOT NULL DEFAULT '',
    state           TEXT      NOT NULL DEFAULT 'open',
    head_branch     TEXT      NOT NULL,
    base_branch     TEXT      NOT NULL,
    head_sha        TEXT      NOT NULL,
    author_login    TEXT      NOT NULL DEFAULT '',
    spec_coverage   DOUBLE PRECISION,  -- nullable
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (repository_id, number)
);

CREATE TABLE mapping_cache (
    id                BIGSERIAL PRIMARY KEY,
    pull_request_id   BIGINT    NOT NULL REFERENCES pull_requests(id) ON DELETE CASCADE,
    head_sha          TEXT      NOT NULL,
    specmap_json      JSONB     NOT NULL,
    spec_coverage     DOUBLE PRECISION,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (pull_request_id, head_sha)
);

-- Indexes for common queries.
CREATE INDEX idx_pull_requests_repo_state ON pull_requests (repository_id, state);
CREATE INDEX idx_mapping_cache_pr_sha ON mapping_cache (pull_request_id, head_sha);
