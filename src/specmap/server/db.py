"""SQLite database layer."""

from __future__ import annotations

import logging
import sqlite3
from importlib import resources
from typing import Any

logger = logging.getLogger("specmap.server")


class Database:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path, check_same_thread=False, timeout=5)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")

    def initialize(self):
        self._migrate()
        schema = resources.files("specmap.server").joinpath("schema.sql").read_text()
        self.conn.executescript(schema)

    def close(self):
        self.conn.close()

    # --- Migration ---

    def _migrate(self):
        """Migrate from github_id schema to provider+provider_id if needed."""
        try:
            cols = [
                row[1]
                for row in self.conn.execute("PRAGMA table_info(users)").fetchall()
            ]
        except sqlite3.OperationalError:
            return  # Table doesn't exist yet, fresh DB

        if "github_id" not in cols:
            return  # Already migrated or fresh

        logger.info("Migrating database: github_id -> provider+provider_id")
        self.conn.execute("PRAGMA foreign_keys=OFF")
        try:
            # --- Users ---
            self.conn.execute(
                """CREATE TABLE users_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    provider_id INTEGER NOT NULL,
                    login TEXT NOT NULL,
                    name TEXT DEFAULT '',
                    avatar_url TEXT DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                    UNIQUE(provider, provider_id)
                )"""
            )
            self.conn.execute(
                """INSERT INTO users_new (id, provider, provider_id, login, name, avatar_url, created_at, updated_at)
                   SELECT id, 'github', github_id, login, name, avatar_url, created_at, updated_at FROM users"""
            )
            self.conn.execute("DROP TABLE users")
            self.conn.execute("ALTER TABLE users_new RENAME TO users")

            # --- Repositories ---
            self.conn.execute(
                """CREATE TABLE repositories_new (
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
                )"""
            )
            self.conn.execute(
                """INSERT INTO repositories_new (id, provider, provider_id, owner, name, full_name, private, created_at, updated_at)
                   SELECT id, 'github', github_id, owner, name, full_name, private, created_at, updated_at FROM repositories"""
            )
            self.conn.execute("DROP TABLE repositories")
            self.conn.execute("ALTER TABLE repositories_new RENAME TO repositories")

            self.conn.commit()
            logger.info("Migration complete")
        finally:
            self.conn.execute("PRAGMA foreign_keys=ON")

    # --- Users ---

    def upsert_user(
        self, provider: str, provider_id: int, login: str, name: str, avatar_url: str
    ) -> dict[str, Any]:
        row = self.conn.execute(
            """INSERT INTO users (provider, provider_id, login, name, avatar_url)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT (provider, provider_id) DO UPDATE SET
                 login=excluded.login, name=excluded.name,
                 avatar_url=excluded.avatar_url,
                 updated_at=strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
               RETURNING *""",
            (provider, provider_id, login, name, avatar_url),
        ).fetchone()
        self.conn.commit()
        return dict(row)

    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

    # --- Tokens ---

    def upsert_token(
        self, user_id: int, encrypted_token: bytes, token_type: str = "bearer", scope: str = ""
    ):
        self.conn.execute(
            """INSERT INTO user_tokens (user_id, access_token_encrypted, token_type, scope)
               VALUES (?, ?, ?, ?)
               ON CONFLICT (user_id) DO UPDATE SET
                 access_token_encrypted=excluded.access_token_encrypted,
                 token_type=excluded.token_type, scope=excluded.scope,
                 updated_at=strftime('%Y-%m-%dT%H:%M:%fZ', 'now')""",
            (user_id, encrypted_token, token_type, scope),
        )
        self.conn.commit()

    def get_token(self, user_id: int) -> bytes | None:
        row = self.conn.execute(
            "SELECT access_token_encrypted FROM user_tokens WHERE user_id = ?", (user_id,)
        ).fetchone()
        return bytes(row["access_token_encrypted"]) if row else None

    # --- Repositories ---

    def upsert_repo(
        self, provider: str, provider_id: int, owner: str, name: str, full_name: str, private: bool
    ) -> dict[str, Any]:
        row = self.conn.execute(
            """INSERT INTO repositories (provider, provider_id, owner, name, full_name, private)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT (provider, provider_id) DO UPDATE SET
                 owner=excluded.owner, name=excluded.name,
                 full_name=excluded.full_name, private=excluded.private,
                 updated_at=strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
               RETURNING *""",
            (provider, provider_id, owner, name, full_name, int(private)),
        ).fetchone()
        self.conn.commit()
        return dict(row)

    def get_repo_by_full_name(self, owner: str, name: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM repositories WHERE owner = ? AND name = ?", (owner, name)
        ).fetchone()
        return dict(row) if row else None

    # --- Pull Requests ---

    def upsert_pull(
        self,
        repository_id: int,
        number: int,
        title: str,
        state: str,
        head_branch: str,
        base_branch: str,
        head_sha: str,
        author_login: str,
    ) -> dict[str, Any]:
        row = self.conn.execute(
            """INSERT INTO pull_requests
                 (repository_id, number, title, state, head_branch, base_branch, head_sha, author_login)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (repository_id, number) DO UPDATE SET
                 title=excluded.title, state=excluded.state,
                 head_branch=excluded.head_branch, base_branch=excluded.base_branch,
                 head_sha=excluded.head_sha, author_login=excluded.author_login,
                 updated_at=strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
               RETURNING *""",
            (repository_id, number, title, state, head_branch, base_branch, head_sha, author_login),
        ).fetchone()
        self.conn.commit()
        return dict(row)

    def get_pull(self, repository_id: int, number: int) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM pull_requests WHERE repository_id = ? AND number = ?",
            (repository_id, number),
        ).fetchone()
        return dict(row) if row else None

    # --- Mapping Cache ---

    def get_mapping_cache(self, pull_request_id: int, head_sha: str) -> str | None:
        row = self.conn.execute(
            "SELECT specmap_json FROM mapping_cache WHERE pull_request_id = ? AND head_sha = ?",
            (pull_request_id, head_sha),
        ).fetchone()
        return row["specmap_json"] if row else None

    def upsert_mapping_cache(self, pull_request_id: int, head_sha: str, specmap_json: str):
        self.conn.execute(
            """INSERT INTO mapping_cache (pull_request_id, head_sha, specmap_json)
               VALUES (?, ?, ?)
               ON CONFLICT (pull_request_id, head_sha) DO UPDATE SET
                 specmap_json=excluded.specmap_json""",
            (pull_request_id, head_sha, specmap_json),
        )
        self.conn.commit()

    def delete_mapping_cache(self, pull_request_id: int):
        self.conn.execute(
            "DELETE FROM mapping_cache WHERE pull_request_id = ?", (pull_request_id,)
        )
        self.conn.commit()

    def delete_walkthrough_cache(self, pull_request_id: int):
        self.conn.execute(
            "DELETE FROM walkthrough_cache WHERE pull_request_id = ?", (pull_request_id,)
        )
        self.conn.commit()

    # --- Walkthrough Cache ---

    def get_walkthrough_cache(
        self, pull_request_id: int, head_sha: str, familiarity: int, depth: str
    ) -> str | None:
        row = self.conn.execute(
            """SELECT walkthrough_json FROM walkthrough_cache
               WHERE pull_request_id = ? AND head_sha = ? AND familiarity = ? AND depth = ?""",
            (pull_request_id, head_sha, familiarity, depth),
        ).fetchone()
        return row["walkthrough_json"] if row else None

    def upsert_walkthrough_cache(
        self,
        pull_request_id: int,
        head_sha: str,
        familiarity: int,
        depth: str,
        walkthrough_json: str,
    ):
        self.conn.execute(
            """INSERT INTO walkthrough_cache
                 (pull_request_id, head_sha, familiarity, depth, walkthrough_json)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT (pull_request_id, head_sha, familiarity, depth) DO UPDATE SET
                 walkthrough_json=excluded.walkthrough_json""",
            (pull_request_id, head_sha, familiarity, depth, walkthrough_json),
        )
        self.conn.commit()
