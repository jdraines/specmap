"""FastAPI application — all API routes."""

from __future__ import annotations

import json
import logging
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from specmap import __version__
from specmap.server import auth, github
from specmap.server.config import ServerConfig
from specmap.server.db import Database
from specmap.server.github import GitHubNotFound

logger = logging.getLogger("specmap.server")


def create_app(config: ServerConfig) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db = Database(config.database_path)
        db.initialize()
        app.state.db = db
        app.state.config = config
        async with httpx.AsyncClient(timeout=30) as client:
            app.state.http = client
            logger.info("specmap server started on %s:%d", config.host, config.port)
            yield
        db.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    # Request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        dt = (time.monotonic() - start) * 1000
        logger.info("%s %s %d %.1fms", request.method, request.url.path, response.status_code, dt)
        return response

    # CORS
    if config.cors_origin:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[config.cors_origin],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # --- Helpers ---

    def _db(request: Request) -> Database:
        return request.app.state.db

    def _cfg(request: Request) -> ServerConfig:
        return request.app.state.config

    def _http(request: Request) -> httpx.AsyncClient:
        return request.app.state.http

    def _get_current_user(request: Request) -> dict:
        token = request.cookies.get(auth.COOKIE_SESSION)
        if not token:
            raise _unauthorized("Not authenticated")
        try:
            return auth.validate_jwt(token, config.session_secret)
        except Exception:
            raise _unauthorized("Invalid session")

    def _get_user_token(request: Request, claims: dict) -> str:
        encrypted = _db(request).get_token(claims["uid"])
        if not encrypted:
            raise _unauthorized("No token found")
        return auth.decrypt_token(encrypted, config.encryption_key)

    def _unauthorized(msg: str):
        return HTTPError(401, msg)

    # --- Routes ---

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok", "version": __version__}

    @app.get("/api/v1/auth/login")
    async def login(request: Request):
        url, state = auth.login_url(_cfg(request).base_url, _cfg(request).github_client_id)
        response = Response(status_code=302, headers={"Location": url})
        response.set_cookie(value=state, **auth.state_cookie_kwargs(_cfg(request).secure))
        return response

    @app.get("/api/v1/auth/callback")
    async def callback(request: Request):
        cfg = _cfg(request)
        code = request.query_params.get("code", "")
        state = request.query_params.get("state", "")
        stored_state = request.cookies.get(auth.COOKIE_OAUTH_STATE, "")

        if not state or state != stored_state:
            raise HTTPError(400, "Invalid OAuth state")
        if not code:
            raise HTTPError(400, "Missing code parameter")

        # Exchange code for token
        token_data = await github.exchange_code(
            _http(request), cfg.github_client_id, cfg.github_client_secret, code
        )
        access_token = token_data.get("access_token", "")
        if not access_token:
            raise HTTPError(400, "Failed to exchange code for token")

        # Fetch GitHub user
        gh_user = await github.get_user(_http(request), access_token)

        # Upsert user
        user = _db(request).upsert_user(
            github_id=gh_user["id"],
            login=gh_user["login"],
            name=gh_user.get("name") or "",
            avatar_url=gh_user.get("avatar_url") or "",
        )

        # Store encrypted token
        encrypted = auth.encrypt_token(access_token, cfg.encryption_key)
        _db(request).upsert_token(
            user_id=user["id"],
            encrypted_token=encrypted,
            token_type=token_data.get("token_type", "bearer"),
            scope=token_data.get("scope", ""),
        )

        # Create JWT session
        jwt_token = auth.create_jwt(
            user["id"], user["login"], user["avatar_url"], cfg.session_secret
        )

        response = Response(status_code=302, headers={"Location": cfg.frontend_url})
        response.set_cookie(value=jwt_token, **auth.session_cookie_kwargs(cfg.secure))
        response.delete_cookie(auth.COOKIE_OAUTH_STATE, path="/")
        return response

    @app.post("/api/v1/auth/logout")
    async def logout(request: Request):
        _get_current_user(request)
        response = JSONResponse({"message": "logged out"})
        response.delete_cookie(auth.COOKIE_SESSION, path="/")
        return response

    @app.get("/api/v1/auth/me")
    async def me(request: Request):
        claims = _get_current_user(request)
        user = _db(request).get_user_by_id(claims["uid"])
        if not user:
            raise HTTPError(404, "User not found")
        return _user_response(user)

    @app.get("/api/v1/repos")
    async def list_repos(request: Request):
        claims = _get_current_user(request)
        token = _get_user_token(request, claims)
        repos = await github.list_repos(_http(request), token)
        result = []
        for r in repos:
            db_repo = _db(request).upsert_repo(
                github_id=r["id"],
                owner=r["owner"]["login"],
                name=r["name"],
                full_name=r["full_name"],
                private=r["private"],
            )
            result.append(_repo_response(db_repo))
        return result

    @app.get("/api/v1/repos/{owner}/{repo}")
    async def get_repo(request: Request, owner: str, repo: str):
        claims = _get_current_user(request)
        token = _get_user_token(request, claims)
        r = await github.get_repo(_http(request), token, owner, repo)
        db_repo = _db(request).upsert_repo(
            github_id=r["id"],
            owner=r["owner"]["login"],
            name=r["name"],
            full_name=r["full_name"],
            private=r["private"],
        )
        return _repo_response(db_repo)

    @app.get("/api/v1/repos/{owner}/{repo}/pulls")
    async def list_pulls(request: Request, owner: str, repo: str):
        claims = _get_current_user(request)
        token = _get_user_token(request, claims)
        # Ensure repo in DB
        r = await github.get_repo(_http(request), token, owner, repo)
        db_repo = _db(request).upsert_repo(
            github_id=r["id"],
            owner=r["owner"]["login"],
            name=r["name"],
            full_name=r["full_name"],
            private=r["private"],
        )
        pulls = await github.list_pulls(_http(request), token, owner, repo)
        result = []
        for p in pulls:
            db_pull = _db(request).upsert_pull(
                repository_id=db_repo["id"],
                number=p["number"],
                title=p["title"],
                state=p["state"],
                head_branch=p["head"]["ref"],
                base_branch=p["base"]["ref"],
                head_sha=p["head"]["sha"],
                author_login=p.get("user", {}).get("login", ""),
            )
            result.append(_pull_response(db_pull))
        return result

    @app.get("/api/v1/repos/{owner}/{repo}/pulls/{number}")
    async def get_pull(request: Request, owner: str, repo: str, number: int):
        claims = _get_current_user(request)
        token = _get_user_token(request, claims)
        # Ensure repo in DB
        r = await github.get_repo(_http(request), token, owner, repo)
        db_repo = _db(request).upsert_repo(
            github_id=r["id"],
            owner=r["owner"]["login"],
            name=r["name"],
            full_name=r["full_name"],
            private=r["private"],
        )
        p = await github.get_pull(_http(request), token, owner, repo, number)
        db_pull = _db(request).upsert_pull(
            repository_id=db_repo["id"],
            number=p["number"],
            title=p["title"],
            state=p["state"],
            head_branch=p["head"]["ref"],
            base_branch=p["base"]["ref"],
            head_sha=p["head"]["sha"],
            author_login=p.get("user", {}).get("login", ""),
        )
        return _pull_response(db_pull)

    @app.get("/api/v1/repos/{owner}/{repo}/pulls/{number}/files")
    async def list_pull_files(request: Request, owner: str, repo: str, number: int):
        claims = _get_current_user(request)
        token = _get_user_token(request, claims)
        files = await github.list_pull_files(_http(request), token, owner, repo, number)
        return [
            {
                "filename": f["filename"],
                "status": f["status"],
                "additions": f["additions"],
                "deletions": f["deletions"],
                "changes": f["changes"],
                "patch": f.get("patch", ""),
            }
            for f in files
        ]

    @app.get("/api/v1/repos/{owner}/{repo}/pulls/{number}/file-source")
    async def get_file_source(request: Request, owner: str, repo: str, number: int):
        claims = _get_current_user(request)
        token = _get_user_token(request, claims)
        path = request.query_params.get("path", "")
        if not path:
            raise HTTPError(400, "Missing path parameter")
        # Get PR to find base branch
        p = await github.get_pull(_http(request), token, owner, repo, number)
        base_ref = p["base"]["ref"]
        try:
            content = await github.get_file_content(
                _http(request), token, owner, repo, path, base_ref
            )
            return {"content": content.decode("utf-8", errors="replace")}
        except GitHubNotFound:
            raise HTTPError(404, "File not found")

    @app.get("/api/v1/repos/{owner}/{repo}/pulls/{number}/annotations")
    async def get_annotations(request: Request, owner: str, repo: str, number: int):
        claims = _get_current_user(request)
        token = _get_user_token(request, claims)
        db = _db(request)

        # Ensure repo and PR in DB
        r = await github.get_repo(_http(request), token, owner, repo)
        db_repo = _db(request).upsert_repo(
            github_id=r["id"],
            owner=r["owner"]["login"],
            name=r["name"],
            full_name=r["full_name"],
            private=r["private"],
        )
        p = await github.get_pull(_http(request), token, owner, repo, number)
        db_pull = db.upsert_pull(
            repository_id=db_repo["id"],
            number=p["number"],
            title=p["title"],
            state=p["state"],
            head_branch=p["head"]["ref"],
            base_branch=p["base"]["ref"],
            head_sha=p["head"]["sha"],
            author_login=p.get("user", {}).get("login", ""),
        )

        head_sha = db_pull["head_sha"]

        # Check cache
        cached = db.get_mapping_cache(db_pull["id"], head_sha)
        if cached:
            return json.loads(cached)

        # Fetch .specmap/{sanitized_branch}.json from repo at head SHA
        branch = db_pull["head_branch"]
        sanitized = branch.replace("/", "--")
        specmap_path = f".specmap/{sanitized}.json"

        try:
            content = await github.get_file_content(
                _http(request), token, owner, repo, specmap_path, head_sha
            )
            specmap_data = json.loads(content)
        except GitHubNotFound:
            # No specmap file — return empty annotations
            specmap_data = _empty_specmap(branch, db_pull)
        except (json.JSONDecodeError, UnicodeDecodeError):
            specmap_data = _empty_specmap(branch, db_pull)

        # Cache it
        db.upsert_mapping_cache(db_pull["id"], head_sha, json.dumps(specmap_data))

        return specmap_data

    @app.get("/api/v1/repos/{owner}/{repo}/pulls/{number}/specs/{path:path}")
    async def get_spec_content(request: Request, owner: str, repo: str, number: int, path: str):
        claims = _get_current_user(request)
        token = _get_user_token(request, claims)
        p = await github.get_pull(_http(request), token, owner, repo, number)
        head_sha = p["head"]["sha"]
        try:
            content = await github.get_file_content(
                _http(request), token, owner, repo, path, head_sha
            )
            return {"path": path, "content": content.decode("utf-8", errors="replace")}
        except GitHubNotFound:
            raise HTTPError(404, "Spec file not found")

    # --- Error handling ---

    class HTTPError(Exception):
        def __init__(self, status_code: int, detail: str):
            self.status_code = status_code
            self.detail = detail

    @app.exception_handler(HTTPError)
    async def http_error_handler(request: Request, exc: HTTPError):
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

    # --- Response helpers ---

    def _user_response(u: dict) -> dict:
        return {
            "id": u["id"],
            "github_id": u["github_id"],
            "login": u["login"],
            "name": u["name"] or "",
            "avatar_url": u["avatar_url"] or "",
            "created_at": u["created_at"],
            "updated_at": u["updated_at"],
        }

    def _repo_response(r: dict) -> dict:
        return {
            "id": r["id"],
            "github_id": r["github_id"],
            "owner": r["owner"],
            "name": r["name"],
            "full_name": r["full_name"],
            "private": bool(r["private"]),
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }

    def _pull_response(p: dict) -> dict:
        return {
            "id": p["id"],
            "repository_id": p["repository_id"],
            "number": p["number"],
            "title": p["title"],
            "state": p["state"],
            "head_branch": p["head_branch"],
            "base_branch": p["base_branch"],
            "head_sha": p["head_sha"],
            "author_login": p["author_login"] or "",
            "created_at": p["created_at"],
            "updated_at": p["updated_at"],
        }

    def _empty_specmap(branch: str, db_pull: dict) -> dict:
        return {
            "version": 2,
            "branch": branch,
            "base_branch": db_pull["base_branch"],
            "head_sha": db_pull["head_sha"],
            "updated_at": "",
            "updated_by": "",
            "annotations": [],
            "ignore_patterns": [],
        }

    # Mount SPA if static_dir is set (must be last)
    if config.static_dir:
        from specmap.server.spa import mount_spa

        mount_spa(app, config.static_dir)

    return app
