"""Server configuration loaded from environment variables."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from specmap.config import CoreConfig
from specmap.server.auth import generate_secret

logger = logging.getLogger("specmap.server")


@dataclass
class ServerConfig:
    core: CoreConfig
    session_secret: str
    encryption_key: str
    # OAuth (optional)
    github_client_id: str = ""
    github_client_secret: str = ""
    gitlab_client_id: str = ""
    gitlab_client_secret: str = ""
    # Server
    base_url: str = ""
    cors_origin: str = ""
    frontend_url: str = ""
    database_path: str = ".specmap/specmap.db"
    port: int = 8080
    host: str = "127.0.0.1"
    static_dir: str = ""
    # Derived
    secure: bool = field(init=False)

    def __post_init__(self):
        if not self.base_url:
            self.base_url = f"http://localhost:{self.port}"
        self.secure = self.base_url.startswith("https://")
        if not self.frontend_url:
            self.frontend_url = self.cors_origin or self.base_url

    @classmethod
    def from_env(cls, **overrides) -> ServerConfig:
        def opt(key: str, default: str = "") -> str:
            return overrides.get(key.lower()) or os.environ.get(key, default)

        core = CoreConfig.load()

        # Auto-generate secrets for local dev convenience
        session_secret = opt("SESSION_SECRET")
        if not session_secret:
            session_secret = generate_secret(32)
            logger.info("SESSION_SECRET not set, auto-generated for this session")
        if len(session_secret) < 32:
            raise ValueError("SESSION_SECRET must be at least 32 characters")

        encryption_key = opt("ENCRYPTION_KEY")
        if not encryption_key:
            encryption_key = generate_secret(32)
            logger.info("ENCRYPTION_KEY not set, auto-generated for this session")
        if len(encryption_key) != 64:
            raise ValueError("ENCRYPTION_KEY must be exactly 64 hex characters (32 bytes)")

        port_str = opt("PORT")
        port = int(port_str) if port_str else 8080

        host = opt("HOST", "127.0.0.1")
        database_path = opt("DATABASE_PATH", ".specmap/specmap.db")

        return cls(
            core=core,
            session_secret=session_secret,
            encryption_key=encryption_key,
            github_client_id=opt("GITHUB_CLIENT_ID"),
            github_client_secret=opt("GITHUB_CLIENT_SECRET"),
            gitlab_client_id=opt("GITLAB_CLIENT_ID"),
            gitlab_client_secret=opt("GITLAB_CLIENT_SECRET"),
            base_url=opt("BASE_URL"),
            cors_origin=opt("CORS_ORIGIN"),
            frontend_url=opt("FRONTEND_URL"),
            database_path=database_path,
            port=port,
            host=host,
            static_dir=opt("STATIC_DIR"),
        )
