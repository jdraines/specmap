"""Server configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class ServerConfig:
    github_client_id: str
    github_client_secret: str
    session_secret: str
    encryption_key: str
    base_url: str = ""
    cors_origin: str = ""
    frontend_url: str = ""
    database_path: str = "./specmap.db"
    port: int = 8080
    host: str = "0.0.0.0"
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
        def req(key: str) -> str:
            val = overrides.get(key.lower()) or os.environ.get(key, "")
            if not val:
                raise ValueError(f"Required environment variable {key} is not set")
            return val

        def opt(key: str, default: str = "") -> str:
            return overrides.get(key.lower()) or os.environ.get(key, default)

        session_secret = req("SESSION_SECRET")
        if len(session_secret) < 32:
            raise ValueError("SESSION_SECRET must be at least 32 characters")

        encryption_key = req("ENCRYPTION_KEY")
        if len(encryption_key) != 64:
            raise ValueError("ENCRYPTION_KEY must be exactly 64 hex characters (32 bytes)")

        port = int(opt("PORT", "8080"))

        return cls(
            github_client_id=req("GITHUB_CLIENT_ID"),
            github_client_secret=req("GITHUB_CLIENT_SECRET"),
            session_secret=session_secret,
            encryption_key=encryption_key,
            base_url=opt("BASE_URL"),
            cors_origin=opt("CORS_ORIGIN"),
            frontend_url=opt("FRONTEND_URL"),
            database_path=opt("DATABASE_PATH", "./specmap.db"),
            port=port,
            host=opt("HOST", "0.0.0.0"),
            static_dir=opt("STATIC_DIR"),
        )
