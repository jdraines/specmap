"""OAuth, JWT, and token encryption utilities."""

from __future__ import annotations

import os
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

COOKIE_SESSION = "specmap_session"
COOKIE_OAUTH_STATE = "specmap_oauth_state"
SESSION_DURATION = timedelta(hours=1)
GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"


def create_jwt(user_id: int, login: str, avatar_url: str, secret: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "uid": user_id,
        "login": login,
        "avatar": avatar_url,
        "iss": "specmap",
        "iat": now,
        "exp": now + SESSION_DURATION,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def validate_jwt(token: str, secret: str) -> dict:
    return jwt.decode(token, secret, algorithms=["HS256"], issuer="specmap")


def encrypt_token(plaintext: str, hex_key: str) -> bytes:
    key = bytes.fromhex(hex_key)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return nonce + ciphertext


def decrypt_token(data: bytes, hex_key: str) -> str:
    key = bytes.fromhex(hex_key)
    aesgcm = AESGCM(key)
    nonce = data[:12]
    ciphertext = data[12:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode()


def login_url(base_url: str, client_id: str) -> tuple[str, str]:
    """Return (authorize_url, state_value)."""
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": client_id,
        "redirect_uri": f"{base_url}/api/v1/auth/callback",
        "scope": "repo",
        "state": state,
    }
    return f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}", state


def session_cookie_kwargs(secure: bool) -> dict:
    return {
        "key": COOKIE_SESSION,
        "httponly": True,
        "secure": secure,
        "samesite": "lax",
        "max_age": int(SESSION_DURATION.total_seconds()),
        "path": "/",
    }


def state_cookie_kwargs(secure: bool) -> dict:
    return {
        "key": COOKIE_OAUTH_STATE,
        "httponly": True,
        "secure": secure,
        "samesite": "lax",
        "max_age": 600,
        "path": "/",
    }
