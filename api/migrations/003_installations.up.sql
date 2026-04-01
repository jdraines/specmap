CREATE TABLE installations (
    id                    BIGSERIAL PRIMARY KEY,
    github_id             BIGINT    NOT NULL UNIQUE,
    account_login         TEXT      NOT NULL,
    account_type          TEXT      NOT NULL DEFAULT 'User',
    repository_selection  TEXT      NOT NULL DEFAULT 'selected',
    suspended_at          TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_installations_account ON installations (account_login);
