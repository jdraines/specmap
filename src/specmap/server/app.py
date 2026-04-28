"""FastAPI application — all API routes."""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.responses import StreamingResponse

from specmap import __version__
from specmap.config import SpecmapConfig, save_user_config, user_config_path, user_data_path, _load_toml
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
)

from specmap.llm.chat_agent import ChatDeps, chat_agent
from specmap.llm.retry import resilient_agent_call
from specmap.llm.code_review_agent import CodeReviewDeps, review_agent, cross_boundary_agent, consolidation_agent
from specmap.llm.code_review_prompts import build_code_review_prompt, build_chunk_review_prompt, build_consolidation_prompt, build_cross_boundary_prompt
from specmap.llm.chat_prompts import build_chat_messages
from specmap.llm.client import LLMClient
from specmap.llm.walkthrough_prompts import build_walkthrough_prompt
from specmap.llm.walkthrough_schemas import WalkthroughResponse
from specmap.server import auth
from specmap.server.config import ServerConfig
from specmap.server.db import Database
from specmap.server.forge import (
    ForgeNotFound,
    ForgeProvider,
    detect_auth_mode,
    detect_forge,
    detect_repo_full_name,
    resolve_token,
)
from specmap.server.generate import generate_full, generate_lite
from specmap.server.github import GitHubProvider
from specmap.server.gitlab import GitLabProvider
from specmap.server.spa import mount_spa
from specmap.state.models import CodeReviewFile, SpecmapFile as SpecmapFileModel, WalkthroughFile
from specmap.state.specmap_file import SpecmapFileManager, _ensure_gitignore

logger = logging.getLogger("specmap.server")


def _build_provider(provider_name: str, base_url: str, config: ServerConfig) -> ForgeProvider:
    if provider_name == "gitlab":
        return GitLabProvider(base_url)
    # Default: GitHub (including GHE)
    if base_url != "https://api.github.com":
        return GitHubProvider(base_url)
    return GitHubProvider()


def create_app(config: ServerConfig | None = None) -> FastAPI:
    if config is None:
        config = ServerConfig.from_env()
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db_dir = os.path.dirname(config.database_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
            _ensure_gitignore(Path(db_dir))
        db = Database(config.database_path)
        db.initialize()
        app.state.db = db
        app.state.config = config

        # Auto-detect forge
        provider_name, base_url = detect_forge()
        provider = _build_provider(provider_name, base_url, config)
        app.state.provider = provider
        app.state.auth_mode = detect_auth_mode(config, provider_name)
        app.state.current_repo = detect_repo_full_name()
        if app.state.current_repo:
            logger.info("Local repo detected: %s (annotations will persist to .specmap/)", app.state.current_repo)
        else:
            logger.info("No local repo detected — annotations will not be saved to disk")

        # PAT mode: resolve token on startup (pass user config for forge tokens)
        _user_cfg: SpecmapConfig | None = None
        _upath = user_config_path()
        if _upath.exists():
            _user_cfg = _load_toml(_upath)

        app.state.forge_token: str | None = None
        if app.state.auth_mode == "pat":
            app.state.forge_token = resolve_token(provider_name, user_config=_user_cfg)
            if app.state.forge_token:
                logger.info("PAT resolved for %s", provider_name)
            else:
                logger.warning(
                    "PAT mode but no token found for %s — set %s or use the web UI to enter one",
                    provider_name,
                    "GITHUB_TOKEN/gh auth token" if provider_name == "github" else "GITLAB_TOKEN/glab auth login",
                )

        async with httpx.AsyncClient(timeout=30) as client:
            app.state.http = client

            # In PAT mode with a token, auto-create a session user
            if app.state.auth_mode == "pat" and app.state.forge_token:
                try:
                    user_data = await provider.get_user(client, app.state.forge_token)
                    pat_user = db.upsert_user(
                        provider=provider.name,
                        provider_id=user_data["id"],
                        login=user_data["login"],
                        name=user_data["name"],
                        avatar_url=user_data["avatar_url"],
                    )
                    app.state.pat_user = pat_user
                    logger.info(
                        "Authenticated as %s via PAT (%s)", user_data["login"], provider.name
                    )
                except Exception as e:
                    logger.warning("PAT token validation failed: %s", e)
                    app.state.forge_token = None
                    app.state.pat_user = None
            else:
                app.state.pat_user = None

            logger.info(
                "specmap server started on %s:%d (forge=%s, auth=%s)",
                config.host,
                config.port,
                provider.name,
                app.state.auth_mode,
            )
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
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["Content-Type", "Authorization"],
        )

    # Security response headers
    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'sha256-wCZJjGQ5Do75oxxZ/g62ubIA/lKTcdliHCxZWhvztnc='; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' https://avatars.githubusercontent.com https://secure.gravatar.com https://gitlab.com https://*.gitlab.com data:; "
            "connect-src 'self'"
        )
        if config.secure:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response

    # --- Helpers ---

    def _db(request: Request) -> Database:
        return request.app.state.db

    def _cfg(request: Request) -> ServerConfig:
        return request.app.state.config

    def _http(request: Request) -> httpx.AsyncClient:
        return request.app.state.http

    def _provider(request: Request) -> ForgeProvider:
        return request.app.state.provider

    def _get_current_user(request: Request) -> dict:
        """Validate session. In PAT mode with auto-auth, synthesize claims."""
        token = request.cookies.get(auth.COOKIE_SESSION)
        if token:
            try:
                return auth.validate_jwt(token, config.session_secret)
            except Exception:
                pass

        # PAT mode auto-auth: if we have a pat_user, treat as authenticated
        if request.app.state.auth_mode == "pat" and request.app.state.pat_user:
            user = request.app.state.pat_user
            return {
                "uid": user["id"],
                "login": user["login"],
                "avatar": user["avatar_url"],
                "provider": request.app.state.provider.name,
            }

        raise _unauthorized("Not authenticated")

    def _get_forge_token(request: Request, claims: dict) -> str:
        """Get forge token for API calls. PAT mode uses startup token; OAuth uses DB."""
        if request.app.state.auth_mode == "pat":
            token = request.app.state.forge_token
            if token:
                return token
            raise _unauthorized("No forge token configured")
        # OAuth mode: decrypt from DB
        encrypted = _db(request).get_token(claims["uid"])
        if not encrypted:
            raise _unauthorized("No token found")
        return auth.decrypt_token(encrypted, config.encryption_key)

    def _unauthorized(msg: str):
        return HTTPError(401, msg)

    # --- Input validation helpers ---

    _BRANCH_RE = re.compile(r"^[\w./_-]+$")

    def _safe_branch(branch: str) -> str:
        """Validate and sanitize a branch name for use in file paths."""
        if not branch or ".." in branch or "\x00" in branch or not _BRANCH_RE.match(branch):
            raise HTTPError(400, f"Invalid branch name: {branch!r}")
        return branch.replace("/", "--")

    def _safe_spec_path(spec_path: str) -> str:
        """Validate a spec file path to prevent traversal."""
        if not spec_path or "\x00" in spec_path:
            raise HTTPError(400, "Invalid spec path")
        from posixpath import normpath
        normalized = normpath(spec_path)
        if normalized.startswith("/") or normalized.startswith(".."):
            raise HTTPError(400, "Invalid spec path")
        return normalized

    # --- Annotation / Walkthrough loading helpers ---

    def _is_local(request: Request, owner: str, repo: str) -> bool:
        return request.app.state.current_repo == f"{owner}/{repo}"

    def _file_mgr() -> SpecmapFileManager:
        return SpecmapFileManager(".")

    def _user_file_mgr(request: Request, owner: str, repo: str) -> SpecmapFileManager:
        """File manager for user-level fallback storage (~/.local/share/specmap/)."""
        provider_name = _provider(request).name
        root = user_data_path() / "repos" / provider_name / owner / repo
        return SpecmapFileManager(str(root))

    def _get_file_mgr(request: Request, owner: str, repo: str) -> SpecmapFileManager:
        """Return the local file manager if in-repo, otherwise the user-level fallback."""
        if _is_local(request, owner, repo):
            return _file_mgr()
        return _user_file_mgr(request, owner, repo)

    async def _load_annotations(request: Request, provider: ForgeProvider, token: str,
                                owner: str, repo: str, branch: str, head_sha: str) -> dict:
        """Load annotations: forge API → local .specmap/ → user data dir, newest wins."""
        remote_data = None
        sanitized = _safe_branch(branch)
        specmap_path = f".specmap/{sanitized}.json"
        try:
            content = await provider.get_file_content(
                _http(request), token, owner, repo, specmap_path, head_sha
            )
            remote_data = json.loads(content)
        except (ForgeNotFound, json.JSONDecodeError, UnicodeDecodeError):
            pass

        # Check local repo .specmap/ and user data dir
        local_data = None
        candidates: list[SpecmapFileManager] = []
        if _is_local(request, owner, repo):
            candidates.append(_file_mgr())
        candidates.append(_user_file_mgr(request, owner, repo))

        for mgr in candidates:
            local_specmap = mgr.load(branch)
            if local_specmap.annotations:
                candidate_data = json.loads(local_specmap.model_dump_json())
                if local_data is None:
                    local_data = candidate_data
                elif candidate_data.get("updated_at", "") > local_data.get("updated_at", ""):
                    local_data = candidate_data

        if remote_data and local_data:
            r_time = remote_data.get("updated_at", "")
            l_time = local_data.get("updated_at", "")
            return remote_data if r_time >= l_time else local_data
        return remote_data or local_data

    async def _load_walkthrough(request: Request, provider: ForgeProvider, token: str,
                                owner: str, repo: str, branch: str, head_sha: str,
                                familiarity: int, depth: str) -> dict | None:
        """Load walkthrough: forge API → local .specmap/ → user data dir, newest wins."""
        remote_data = None
        sanitized = _safe_branch(branch)
        wt_path = f".specmap/{sanitized}.walkthrough.f{familiarity}.{depth}.json"
        try:
            content = await provider.get_file_content(
                _http(request), token, owner, repo, wt_path, head_sha
            )
            remote_data = json.loads(content)
        except (ForgeNotFound, json.JSONDecodeError, UnicodeDecodeError):
            pass

        # Check local repo .specmap/ and user data dir
        local_data = None
        candidates: list[SpecmapFileManager] = []
        if _is_local(request, owner, repo):
            candidates.append(_file_mgr())
        candidates.append(_user_file_mgr(request, owner, repo))

        for mgr in candidates:
            local_wt = mgr.load_walkthrough(branch, familiarity, depth)
            if local_wt:
                candidate_data = json.loads(local_wt.model_dump_json())
                if local_data is None:
                    local_data = candidate_data
                elif candidate_data.get("updated_at", "") > local_data.get("updated_at", ""):
                    local_data = candidate_data

        if remote_data and local_data:
            r_time = remote_data.get("updated_at", "")
            l_time = local_data.get("updated_at", "")
            return remote_data if r_time >= l_time else local_data
        return remote_data or local_data

    # --- Routes ---

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok", "version": __version__}

    # --- Auth routes ---

    @app.get("/api/v1/auth/status")
    async def auth_status(request: Request):
        provider = _provider(request)
        mode = request.app.state.auth_mode
        # Check if user is authenticated
        try:
            claims = _get_current_user(request)
            user = _db(request).get_user_by_id(claims["uid"])
            if user:
                return {
                    "authenticated": True,
                    "auth_mode": mode,
                    "provider": provider.name,
                    "user": _user_response(user),
                    "current_repo": request.app.state.current_repo,
                }
        except HTTPError:
            pass

        # Not authenticated
        hint = ""
        if mode == "pat":
            env_var = "GITHUB_TOKEN" if provider.name == "github" else "GITLAB_TOKEN"
            cli_cmd = "gh auth token" if provider.name == "github" else "glab auth login"
            hint = (
                f"specmap runs locally — your token is only used to call the {provider.name} API. "
                f"Set {env_var} or run `{cli_cmd}`, then restart the server. "
                f"Or enter a token below."
            )
        token_hint = ""
        if mode == "pat":
            if provider.name == "gitlab":
                token_hint = "legacy PAT \u00b7 needs api scope"
            else:
                token_hint = "classic token \u00b7 needs repo scope"

        return {
            "authenticated": False,
            "auth_mode": mode,
            "provider": provider.name,
            "setup_hint": hint,
            "token_hint": token_hint,
            "current_repo": request.app.state.current_repo,
        }

    @app.post("/api/v1/auth/token")
    async def submit_token(request: Request):
        """Manual PAT entry from frontend."""
        body = await request.json()
        token = body.get("token", "").strip()
        if not token:
            raise HTTPError(400, "Token is required")

        provider = _provider(request)
        try:
            user_data = await provider.get_user(_http(request), token)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                if provider.name == "gitlab":
                    raise HTTPError(400, "Token lacks required scopes. GitLab tokens need at least: api or read_api + read_user + read_repository.")
                raise HTTPError(400, "Token lacks required permissions (403 Forbidden).")
            raise HTTPError(400, f"Invalid token — could not authenticate ({e.response.status_code}).")
        except Exception:
            raise HTTPError(400, "Invalid token — could not authenticate with forge.")

        db = _db(request)
        user = db.upsert_user(
            provider=provider.name,
            provider_id=user_data["id"],
            login=user_data["login"],
            name=user_data["name"],
            avatar_url=user_data["avatar_url"],
        )

        # Store the token for this session
        request.app.state.forge_token = token
        request.app.state.pat_user = user

        # Create JWT session
        jwt_token = auth.create_jwt(
            user["id"], user["login"], user["avatar_url"], provider.name, config.session_secret
        )
        response = JSONResponse({"user": _user_response(user)})
        response.set_cookie(value=jwt_token, **auth.session_cookie_kwargs(config.secure))
        return response

    @app.post("/api/v1/auth/save-token")
    async def save_forge_token(request: Request):
        """Save the current forge token to user config for persistence."""
        claims = _get_current_user(request)
        token = _get_forge_token(request, claims)
        provider = _provider(request)

        cfg = SpecmapConfig()
        if provider.name == "github":
            cfg.forge_github_token = token
        else:
            cfg.forge_gitlab_token = token
        path = save_user_config(cfg)
        return {"saved": True, "path": str(path)}

    @app.get("/api/v1/auth/login/{provider_name}")
    async def login(request: Request, provider_name: str):
        provider = _provider(request)
        if provider_name != provider.name:
            raise HTTPError(400, f"Server is configured for {provider.name}, not {provider_name}")
        cfg = _cfg(request)
        if provider_name == "github":
            client_id = cfg.github_client_id
        else:
            client_id = cfg.gitlab_client_id
        if not client_id:
            raise HTTPError(400, f"OAuth not configured for {provider_name}")
        redirect_uri = f"{cfg.base_url}/api/v1/auth/callback/{provider_name}"
        url, state = provider.oauth_authorize_url(cfg.base_url, client_id, redirect_uri)
        response = Response(status_code=302, headers={"Location": url})
        response.set_cookie(value=state, **auth.state_cookie_kwargs(cfg.secure))
        return response

    @app.get("/api/v1/auth/login")
    async def login_default(request: Request):
        """Backward compat: redirect to provider-specific login."""
        provider = _provider(request)
        return Response(
            status_code=302,
            headers={"Location": f"/api/v1/auth/login/{provider.name}"},
        )

    @app.get("/api/v1/auth/callback/{provider_name}")
    async def callback(request: Request, provider_name: str):
        provider = _provider(request)
        if provider_name != provider.name:
            raise HTTPError(400, "Provider mismatch")
        cfg = _cfg(request)
        code = request.query_params.get("code", "")
        state = request.query_params.get("state", "")
        stored_state = request.cookies.get(auth.COOKIE_OAUTH_STATE, "")

        if not state or state != stored_state:
            raise HTTPError(400, "Invalid OAuth state")
        if not code:
            raise HTTPError(400, "Missing code parameter")

        if provider_name == "github":
            client_id = cfg.github_client_id
            client_secret = cfg.github_client_secret
        else:
            client_id = cfg.gitlab_client_id
            client_secret = cfg.gitlab_client_secret

        redirect_uri = f"{cfg.base_url}/api/v1/auth/callback/{provider_name}"
        token_data = await provider.oauth_exchange_code(
            _http(request), client_id, client_secret, code, redirect_uri
        )
        access_token = token_data.get("access_token", "")
        if not access_token:
            raise HTTPError(400, "Failed to exchange code for token")

        user_data = await provider.get_user(_http(request), access_token)

        user = _db(request).upsert_user(
            provider=provider.name,
            provider_id=user_data["id"],
            login=user_data["login"],
            name=user_data["name"],
            avatar_url=user_data["avatar_url"],
        )

        encrypted = auth.encrypt_token(access_token, cfg.encryption_key)
        _db(request).upsert_token(
            user_id=user["id"],
            encrypted_token=encrypted,
            token_type=token_data.get("token_type", "bearer"),
            scope=token_data.get("scope", ""),
        )

        jwt_token = auth.create_jwt(
            user["id"], user["login"], user["avatar_url"], provider.name, cfg.session_secret
        )

        response = Response(status_code=302, headers={"Location": cfg.frontend_url})
        response.set_cookie(value=jwt_token, **auth.session_cookie_kwargs(cfg.secure))
        response.delete_cookie(auth.COOKIE_OAUTH_STATE, path="/")
        return response

    # Keep old callback route for backward compat
    @app.get("/api/v1/auth/callback")
    async def callback_default(request: Request):
        provider = _provider(request)
        # Forward query params
        qs = str(request.url.query)
        location = f"/api/v1/auth/callback/{provider.name}"
        if qs:
            location += f"?{qs}"
        return Response(status_code=302, headers={"Location": location})

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

    # --- Capabilities ---

    @app.get("/api/v1/capabilities")
    async def capabilities(request: Request):
        cfg = _cfg(request)
        has_llm = bool(cfg.core.api_key)
        return {"walkthrough": has_llm, "annotations": has_llm, "code_review": has_llm}

    # --- Settings ---

    _SAFE_SETTINGS = {"model"}

    @app.get("/api/v1/settings")
    async def get_settings(request: Request):
        _get_current_user(request)
        cfg = _cfg(request)
        return {"model": cfg.core.model}

    @app.post("/api/v1/settings")
    async def update_settings(request: Request):
        _get_current_user(request)
        body = await request.json()

        model_val = str(body.get("model", "")).strip() if "model" in body else ""
        if not model_val:
            raise HTTPError(400, "No valid settings provided")

        # Save to user config file (merges with existing)
        save_cfg = SpecmapConfig(model=model_val)
        save_user_config(save_cfg)

        # Reload the running config so changes take effect immediately
        cfg = _cfg(request)
        from dataclasses import replace
        new_core = replace(cfg.core, model=model_val)
        new_server_cfg = type(cfg)(
            **{**vars(cfg), "core": new_core}
        )
        request.app.state.config = new_server_cfg

        return {"model": new_core.model}

    # --- Data routes ---

    @app.get("/api/v1/repos")
    async def list_repos(request: Request):
        claims = _get_current_user(request)
        token = _get_forge_token(request, claims)
        provider = _provider(request)
        http = _http(request)
        db = _db(request)

        # Parse pagination / search params
        try:
            page = max(1, int(request.query_params.get("page", "1")))
        except (ValueError, TypeError):
            page = 1
        try:
            per_page = max(1, min(100, int(request.query_params.get("per_page", "20"))))
        except (ValueError, TypeError):
            per_page = 20
        search = request.query_params.get("search", "").strip()

        page_data = await provider.list_repos_page(
            http, token,
            page=page, per_page=per_page, search=search,
            login=claims.get("login", ""),
        )

        # Upsert repos into DB + fetch PRs only for this page
        db_repos = []
        for r in page_data["items"]:
            db_repo = db.upsert_repo(
                provider=provider.name,
                provider_id=r["id"],
                owner=r["owner"],
                name=r["name"],
                full_name=r["full_name"],
                private=r["private"],
            )
            db_repos.append(db_repo)

        async def _fetch_recent_pulls(r: dict) -> list[dict]:
            try:
                return await provider.list_pulls(
                    http, token, r["owner"], r["name"], per_page=3,
                )
            except Exception:
                return []

        pulls_per_repo = await asyncio.gather(
            *[_fetch_recent_pulls(r) for r in db_repos]
        )

        items = []
        for db_repo, pulls in zip(db_repos, pulls_per_repo):
            recent = []
            for p in pulls:
                if p["head_sha"]:
                    recent.append(_pull_response(
                        db.upsert_pull(
                            repository_id=db_repo["id"],
                            number=p["number"],
                            title=p["title"],
                            state=p["state"],
                            head_branch=p["head_branch"],
                            base_branch=p["base_branch"],
                            head_sha=p["head_sha"],
                            author_login=p["author_login"],
                        )
                    ))
                else:
                    # sha not yet available (GitLab async population);
                    # show on dashboard without persisting to DB
                    recent.append({
                        "id": 0,
                        "repository_id": db_repo["id"],
                        "number": p["number"],
                        "title": p["title"],
                        "state": p["state"],
                        "head_branch": p["head_branch"],
                        "base_branch": p["base_branch"],
                        "head_sha": "",
                        "author_login": p.get("author_login", ""),
                        "created_at": "",
                        "updated_at": "",
                    })
            items.append(_repo_response(db_repo, recent_pulls=recent))

        return {
            "items": items,
            "total": page_data["total"],
            "page": page_data["page"],
            "per_page": page_data["per_page"],
            "total_pages": page_data["total_pages"],
        }

    # --- Repo route helpers ---
    # These are called by the catch-all dispatcher below.

    async def _handle_get_repo(request: Request, owner: str, repo: str):
        claims = _get_current_user(request)
        token = _get_forge_token(request, claims)
        provider = _provider(request)
        r = await provider.get_repo(_http(request), token, owner, repo)
        db_repo = _db(request).upsert_repo(
            provider=provider.name,
            provider_id=r["id"],
            owner=r["owner"],
            name=r["name"],
            full_name=r["full_name"],
            private=r["private"],
        )
        return _repo_response(db_repo)

    async def _handle_list_pulls(request: Request, owner: str, repo: str):
        claims = _get_current_user(request)
        token = _get_forge_token(request, claims)
        provider = _provider(request)
        r = await provider.get_repo(_http(request), token, owner, repo)
        db_repo = _db(request).upsert_repo(
            provider=provider.name,
            provider_id=r["id"],
            owner=r["owner"],
            name=r["name"],
            full_name=r["full_name"],
            private=r["private"],
        )
        pulls_list = await provider.list_pulls(_http(request), token, owner, repo)
        result = []
        for p in pulls_list:
            if p["head_sha"]:
                db_pull = _db(request).upsert_pull(
                    repository_id=db_repo["id"],
                    number=p["number"],
                    title=p["title"],
                    state=p["state"],
                    head_branch=p["head_branch"],
                    base_branch=p["base_branch"],
                    head_sha=p["head_sha"],
                    author_login=p["author_login"],
                )
                result.append(_pull_response(db_pull))
            else:
                result.append({
                    "id": 0,
                    "repository_id": db_repo["id"],
                    "number": p["number"],
                    "title": p["title"],
                    "state": p["state"],
                    "head_branch": p["head_branch"],
                    "base_branch": p["base_branch"],
                    "head_sha": "",
                    "author_login": p.get("author_login", ""),
                    "created_at": "",
                    "updated_at": "",
                })
        return result

    async def _handle_get_pull(request: Request, owner: str, repo: str, number: int):
        claims = _get_current_user(request)
        token = _get_forge_token(request, claims)
        provider = _provider(request)
        r = await provider.get_repo(_http(request), token, owner, repo)
        db_repo = _db(request).upsert_repo(
            provider=provider.name,
            provider_id=r["id"],
            owner=r["owner"],
            name=r["name"],
            full_name=r["full_name"],
            private=r["private"],
        )
        p = await provider.get_pull(_http(request), token, owner, repo, number)
        db_pull = _db(request).upsert_pull(
            repository_id=db_repo["id"],
            number=p["number"],
            title=p["title"],
            state=p["state"],
            head_branch=p["head_branch"],
            base_branch=p["base_branch"],
            head_sha=p["head_sha"],
            author_login=p["author_login"],
        )
        return _pull_response(db_pull)

    async def _handle_list_pull_files(request: Request, owner: str, repo: str, number: int):
        claims = _get_current_user(request)
        token = _get_forge_token(request, claims)
        provider = _provider(request)
        return await provider.list_pull_files(_http(request), token, owner, repo, number)

    async def _handle_get_file_source(request: Request, owner: str, repo: str, number: int):
        claims = _get_current_user(request)
        token = _get_forge_token(request, claims)
        provider = _provider(request)
        path = _safe_spec_path(request.query_params.get("path", ""))
        if not path:
            raise HTTPError(400, "Missing path parameter")
        p = await provider.get_pull(_http(request), token, owner, repo, number)
        base_ref = p["base_branch"]
        try:
            content = await provider.get_file_content(
                _http(request), token, owner, repo, path, base_ref
            )
            return {"content": content.decode("utf-8", errors="replace")}
        except ForgeNotFound:
            raise HTTPError(404, "File not found")

    async def _handle_get_annotations(request: Request, owner: str, repo: str, number: int):
        claims = _get_current_user(request)
        token = _get_forge_token(request, claims)
        provider = _provider(request)
        db = _db(request)

        r = await provider.get_repo(_http(request), token, owner, repo)
        db_repo = db.upsert_repo(
            provider=provider.name,
            provider_id=r["id"],
            owner=r["owner"],
            name=r["name"],
            full_name=r["full_name"],
            private=r["private"],
        )
        p = await provider.get_pull(_http(request), token, owner, repo, number)
        db_pull = db.upsert_pull(
            repository_id=db_repo["id"],
            number=p["number"],
            title=p["title"],
            state=p["state"],
            head_branch=p["head_branch"],
            base_branch=p["base_branch"],
            head_sha=p["head_sha"],
            author_login=p["author_login"],
        )

        branch = db_pull["head_branch"]
        head_sha = db_pull["head_sha"]

        data = await _load_annotations(request, provider, token, owner, repo, branch, head_sha)
        return data or _empty_specmap(branch, db_pull)

    async def _handle_get_spec_content(request: Request, owner: str, repo: str, number: int, spec_path: str):
        claims = _get_current_user(request)
        token = _get_forge_token(request, claims)
        provider = _provider(request)
        p = await provider.get_pull(_http(request), token, owner, repo, number)
        head_sha = p["head_sha"]
        try:
            content = await provider.get_file_content(
                _http(request), token, owner, repo, spec_path, head_sha
            )
            return {"path": spec_path, "content": content.decode("utf-8", errors="replace")}
        except ForgeNotFound:
            raise HTTPError(404, "Spec file not found")

    # --- Comments ---

    async def _handle_list_comments(request: Request, owner: str, repo: str, number: int):
        claims = _get_current_user(request)
        token = _get_forge_token(request, claims)
        provider = _provider(request)
        return await provider.list_pull_comments(_http(request), token, owner, repo, number)

    async def _handle_post_comment(request: Request, owner: str, repo: str, number: int):
        claims = _get_current_user(request)
        token = _get_forge_token(request, claims)
        provider = _provider(request)
        data = await request.json()

        body = data.get("body", "").strip()
        if not body:
            raise HTTPError(400, "Comment body required")

        thread_id = data.get("thread_id")
        path = data.get("path")
        line_val = data.get("line")
        side = data.get("side")

        head_sha = None
        if path and not thread_id:
            p = await provider.get_pull(_http(request), token, owner, repo, number)
            head_sha = p["head_sha"]

        result = await provider.post_pull_comment(
            _http(request), token, owner, repo, number,
            body, thread_id=thread_id, path=path, line=line_val,
            side=side, head_sha=head_sha,
        )
        return result

    # --- Generate Annotations ---

    def _sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    async def _handle_generate_annotations(request: Request, owner: str, repo: str, number: int):
        cfg = _cfg(request)
        if not cfg.core.api_key:
            raise HTTPError(503, "LLM not configured. Set SPECMAP_API_KEY.")

        claims = _get_current_user(request)
        token = _get_forge_token(request, claims)
        provider = _provider(request)
        db = _db(request)

        body = await request.json()
        mode = body.get("mode", "full")
        force = body.get("force", False)
        req_timeout = body.get("timeout")
        resume = body.get("resume", False)
        concurrency = max(1, min(8, int(body.get("concurrency", 4))))

        if mode not in ("lite", "full"):
            raise HTTPError(400, 'mode must be "lite" or "full"')

        # Resolve timeout: request body → config → default
        if req_timeout is not None:
            annotate_timeout = max(30, min(1800, int(req_timeout)))
        else:
            annotate_timeout = cfg.core.annotate_timeout

        # Fetch repo + PR
        r = await provider.get_repo(_http(request), token, owner, repo)
        db_repo = db.upsert_repo(
            provider=provider.name,
            provider_id=r["id"],
            owner=r["owner"],
            name=r["name"],
            full_name=r["full_name"],
            private=r["private"],
        )
        p = await provider.get_pull(_http(request), token, owner, repo, number)
        db_pull = db.upsert_pull(
            repository_id=db_repo["id"],
            number=p["number"],
            title=p["title"],
            state=p["state"],
            head_branch=p["head_branch"],
            base_branch=p["base_branch"],
            head_sha=p["head_sha"],
            author_login=p["author_login"],
        )
        head_sha = db_pull["head_sha"]

        branch = db_pull["head_branch"]

        # Check existing annotations — return plain JSON (not SSE)
        if not force and not resume:
            existing = await _load_annotations(request, provider, token, owner, repo, branch, head_sha)
            if existing and existing.get("annotations") and not existing.get("partial"):
                return existing

        # Resume support: load partial result from file and extract already-annotated files
        exclude_files: set[str] | None = None
        cached_annotations: list[dict] = []
        if resume:
            existing = await _load_annotations(request, provider, token, owner, repo, branch, head_sha)
            if existing:
                cached_annotations = existing.get("annotations", [])
                if cached_annotations:
                    exclude_files = {ann["file"] for ann in cached_annotations}

        # Fetch PR files
        pr_files = await provider.list_pull_files(
            _http(request), token, owner, repo, number
        )

        # Stream SSE with progress
        async def event_stream():
            progress_queue: asyncio.Queue = asyncio.Queue()

            async def on_progress(data: dict):
                await progress_queue.put(("progress", data))

            yield _sse("progress", {"phase": "starting", "detail": "Starting annotation generation..."})

            async def run_generate():
                try:
                    if mode == "lite":
                        result = await generate_lite(
                            provider, _http(request), token,
                            owner, repo, pr_files,
                            head_sha, db_pull["head_branch"], db_pull["base_branch"],
                            config=cfg.core,
                            annotate_timeout=annotate_timeout,
                            on_progress=on_progress,
                            exclude_files=exclude_files,
                            concurrency=concurrency,
                        )
                    else:
                        result = await generate_full(
                            provider, _http(request), token,
                            owner, repo, pr_files,
                            head_sha, db_pull["head_branch"], db_pull["base_branch"],
                            config=cfg.core,
                            pr_title=db_pull["title"],
                            annotate_timeout=annotate_timeout,
                            on_progress=on_progress,
                            exclude_files=exclude_files,
                            concurrency=concurrency,
                        )

                    # Merge with cached annotations on resume
                    if cached_annotations:
                        new_files = {ann["file"] for ann in result.get("annotations", [])}
                        merged = [ann for ann in cached_annotations if ann["file"] not in new_files]
                        merged.extend(result.get("annotations", []))
                        result["annotations"] = merged
                        # If no longer partial, clear the flag
                        if not result.get("partial"):
                            result.pop("partial", None)
                            result.pop("completed_batches", None)
                            result.pop("total_batches", None)

                    await progress_queue.put(("complete", result))
                except (TimeoutError, asyncio.CancelledError):
                    await progress_queue.put(("error", {"message": "Annotation generation timed out — the PR may be too large. Try 'lite' mode or increase timeout."}))
                except Exception as e:
                    await progress_queue.put(("error", {"message": str(e)}))

            task = asyncio.create_task(run_generate())

            while True:
                event_type, data = await progress_queue.get()
                if event_type == "complete":
                    # Persist annotations
                    try:
                        sf = SpecmapFileModel.model_validate(data)
                        sf.branch = branch
                        sf.updated_by = "server:generate"
                        path = _get_file_mgr(request, owner, repo).save(sf)
                        logger.info("Saved annotations to %s", path)
                    except Exception as e:
                        logger.error("Failed to save annotations: %s", e)
                    yield _sse("complete", data)
                    break
                elif event_type == "error":
                    yield _sse("error", data)
                    break
                else:
                    yield _sse("progress", data)

            # Ensure task is done
            if not task.done():
                task.cancel()

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    # --- Clear Cache ---

    async def _handle_clear_cache(request: Request, owner: str, repo: str, number: int):
        claims = _get_current_user(request)
        token = _get_forge_token(request, claims)
        provider = _provider(request)

        # Get the branch name for this PR
        p = await provider.get_pull(_http(request), token, owner, repo, number)
        branch = p["head_branch"]

        # Delete cached files
        _get_file_mgr(request, owner, repo).delete_files(branch)

        return {"status": "cleared"}

    # --- Walkthrough ---

    async def _handle_generate_walkthrough(request: Request, owner: str, repo: str, number: int):
        cfg = _cfg(request)
        if not cfg.core.api_key:
            raise HTTPError(503, "LLM not configured. Set SPECMAP_API_KEY.")

        claims = _get_current_user(request)
        token = _get_forge_token(request, claims)
        provider = _provider(request)
        db = _db(request)

        body = await request.json()
        familiarity = body.get("familiarity", 2)
        depth = body.get("depth", "quick")

        if familiarity not in (1, 2, 3):
            raise HTTPError(400, "familiarity must be 1, 2, or 3")
        if depth not in ("quick", "thorough"):
            raise HTTPError(400, 'depth must be "quick" or "thorough"')

        # Fetch repo + PR
        r = await provider.get_repo(_http(request), token, owner, repo)
        db_repo = db.upsert_repo(
            provider=provider.name,
            provider_id=r["id"],
            owner=r["owner"],
            name=r["name"],
            full_name=r["full_name"],
            private=r["private"],
        )
        p = await provider.get_pull(_http(request), token, owner, repo, number)
        db_pull = db.upsert_pull(
            repository_id=db_repo["id"],
            number=p["number"],
            title=p["title"],
            state=p["state"],
            head_branch=p["head_branch"],
            base_branch=p["base_branch"],
            head_sha=p["head_sha"],
            author_login=p["author_login"],
        )
        branch = db_pull["head_branch"]
        head_sha = db_pull["head_sha"]

        # Check existing walkthrough (file is already keyed by familiarity+depth)
        existing_wt = await _load_walkthrough(request, provider, token, owner, repo,
                                              branch, head_sha, familiarity, depth)
        if existing_wt and existing_wt.get("head_sha") == head_sha:
            return existing_wt

        # Get annotations (forge → local file)
        specmap_data = await _load_annotations(request, provider, token, owner, repo, branch, head_sha)
        if not specmap_data:
            specmap_data = _empty_specmap(branch, db_pull)

        annotations_list = specmap_data.get("annotations", [])
        if not annotations_list:
            # Auto-generate annotations via full mode
            try:
                pr_files_for_gen = await provider.list_pull_files(
                    _http(request), token, owner, repo, number
                )
                try:
                    specmap_data = await generate_full(
                        provider, _http(request), token,
                        owner, repo, pr_files_for_gen,
                        head_sha, db_pull["head_branch"], db_pull["base_branch"],
                        config=cfg.core,
                        pr_title=db_pull["title"],
                    )
                except Exception:
                    # Fallback to lite mode
                    specmap_data = await generate_lite(
                        provider, _http(request), token,
                        owner, repo, pr_files_for_gen,
                        head_sha, db_pull["head_branch"], db_pull["base_branch"],
                        config=cfg.core,
                    )
                # Persist generated annotations
                sf = SpecmapFileModel.model_validate(specmap_data)
                sf.branch = branch
                sf.updated_by = "server:generate"
                _get_file_mgr(request, owner, repo).save(sf)
                annotations_list = specmap_data.get("annotations", [])
            except Exception:
                pass

            if not annotations_list:
                raise HTTPError(409, "No annotations available")

        # Fetch file patches
        file_patches = await provider.list_pull_files(_http(request), token, owner, repo, number)

        # Collect unique spec files from annotations and fetch content
        spec_files: set[str] = set()
        for ann in annotations_list:
            for ref in ann.get("refs", []):
                sf = ref.get("spec_file", "")
                if sf:
                    spec_files.add(sf)

        spec_contents: dict[str, str] = {}
        for sf in spec_files:
            try:
                raw = await provider.get_file_content(
                    _http(request), token, owner, repo, sf, head_sha
                )
                spec_contents[sf] = raw.decode("utf-8", errors="replace")
            except ForgeNotFound:
                pass

        # Build prompt and call LLM
        messages = build_walkthrough_prompt(
            pr_title=db_pull["title"],
            head_branch=db_pull["head_branch"],
            base_branch=db_pull["base_branch"],
            annotations=annotations_list,
            file_patches=file_patches,
            spec_contents=spec_contents,
            familiarity=familiarity,
            depth=depth,
        )

        llm_client = LLMClient(cfg.core)
        prompt_text = " ".join(m.get("content", "") for m in messages)
        logger.info("Walkthrough prompt: ~%d estimated tokens", len(prompt_text) // 4)
        result = await llm_client.complete(messages, response_format=WalkthroughResponse)

        # Build response
        steps = []
        for step in result.steps:
            refs = []
            for ref in step.refs:
                refs.append({
                    "id": ref.ref_number,
                    "spec_file": ref.spec_file,
                    "heading": ref.heading,
                    "start_line": 0,
                    "excerpt": ref.excerpt,
                })
            steps.append({
                "step_number": step.step_number,
                "title": step.title,
                "narrative": step.narrative,
                "file": step.file,
                "start_line": step.start_line or 0,
                "end_line": step.end_line or 0,
                "refs": refs,
            })

        walkthrough_data = {
            "version": 1,
            "branch": branch,
            "summary": result.summary,
            "steps": steps,
            "familiarity": familiarity,
            "depth": depth,
            "head_sha": head_sha,
            "updated_at": datetime.datetime.now(datetime.timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
            "updated_by": "server:generate",
        }

        # Persist walkthrough
        wf = WalkthroughFile.model_validate(walkthrough_data)
        _get_file_mgr(request, owner, repo).save_walkthrough(wf)

        return walkthrough_data

    # --- Walkthrough Chat ---

    def _build_chat_model(core_config):
        """Build a pydantic-ai Model from CoreConfig.

        Handles mapping litellm-style model strings (e.g. 'anthropic/claude-sonnet-4-20250514')
        to pydantic-ai's provider system.
        """
        model_str = core_config.model
        api_key = core_config.api_key
        api_base = core_config.api_base

        # Custom base URL → use OpenAI-compatible provider
        if api_base:
            from pydantic_ai.providers.openai import OpenAIProvider
            from pydantic_ai.models.openai import OpenAIModel
            # Strip any provider prefix for the model name
            model_name = model_str.split("/", 1)[-1] if "/" in model_str else model_str
            return OpenAIModel(model_name, provider=OpenAIProvider(
                api_key=api_key, base_url=api_base,
            ))

        # litellm uses 'anthropic/model-name' prefix
        if model_str.startswith("anthropic/"):
            from pydantic_ai.providers.anthropic import AnthropicProvider
            from pydantic_ai.models.anthropic import AnthropicModel
            model_name = model_str.split("/", 1)[1]
            return AnthropicModel(model_name, provider=AnthropicProvider(api_key=api_key))

        # OpenAI models (gpt-4o, etc.) — no prefix or 'openai/' prefix
        if model_str.startswith("openai/"):
            model_name = model_str.split("/", 1)[1]
        else:
            model_name = model_str

        from pydantic_ai.providers.openai import OpenAIProvider
        from pydantic_ai.models.openai import OpenAIModel
        return OpenAIModel(model_name, provider=OpenAIProvider(api_key=api_key))

    async def _handle_walkthrough_chat(request: Request, owner: str, repo: str, number: int):
        cfg = _cfg(request)
        if not cfg.core.api_key:
            raise HTTPError(503, "LLM not configured. Set SPECMAP_API_KEY.")

        claims = _get_current_user(request)
        token = _get_forge_token(request, claims)
        provider = _provider(request)

        body = await request.json()
        step_number = body.get("step_number")
        message = body.get("message", "").strip()
        familiarity = body.get("familiarity", 2)
        depth = body.get("depth", "quick")

        if not step_number or not message:
            raise HTTPError(400, "step_number and message are required")

        # Fetch PR info
        p = await provider.get_pull(_http(request), token, owner, repo, number)
        branch = p["head_branch"]
        head_sha = p["head_sha"]

        # Load existing walkthrough
        wt_data = await _load_walkthrough(
            request, provider, token, owner, repo,
            branch, head_sha, familiarity, depth,
        )
        if not wt_data:
            raise HTTPError(404, "No walkthrough found. Generate one first.")

        steps = wt_data.get("steps", [])
        step_idx = next(
            (i for i, s in enumerate(steps) if s.get("step_number") == step_number),
            None,
        )
        if step_idx is None:
            raise HTTPError(404, f"Step {step_number} not found")

        step = steps[step_idx]

        # Append user message and persist immediately
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        user_msg = {"role": "user", "content": message, "timestamp": now}
        if "chat" not in step:
            step["chat"] = []
        step["chat"].append(user_msg)

        wf = WalkthroughFile.model_validate(wt_data)
        _get_file_mgr(request, owner, repo).save_walkthrough(wf)

        # Load annotations for context
        specmap_data = await _load_annotations(
            request, provider, token, owner, repo, branch, head_sha,
        )
        annotations_list = specmap_data.get("annotations", []) if specmap_data else []

        # Fetch current step's file patch and source
        file_patch = None
        file_source = None
        step_file = step.get("file", "")
        if step_file:
            # Get patch from PR files
            try:
                pr_files = await provider.list_pull_files(
                    _http(request), token, owner, repo, number,
                )
                for pf in pr_files:
                    if pf["filename"] == step_file:
                        file_patch = pf.get("patch", "")
                        break
            except Exception:
                pass

            # Get source content around the step's focus range
            try:
                raw = await provider.get_file_content(
                    _http(request), token, owner, repo, step_file, head_sha,
                )
                source_lines = raw.decode("utf-8", errors="replace").splitlines()
                sl = step.get("start_line", 0)
                el = step.get("end_line", 0)
                if sl and el:
                    ctx_start = max(sl - 51, 0)
                    ctx_end = min(el + 50, len(source_lines))
                    excerpt = source_lines[ctx_start:ctx_end]
                    numbered = [f"{i}: {line}" for i, line in enumerate(excerpt, ctx_start + 1)]
                    file_source = "\n".join(numbered)
                elif len(source_lines) <= 500:
                    numbered = [f"{i}: {line}" for i, line in enumerate(source_lines, 1)]
                    file_source = "\n".join(numbered)
            except (ForgeNotFound, Exception):
                pass

        # Build chat messages (excluding the just-appended user message — it goes as user_prompt)
        chat_history = step.get("chat", [])[:-1]  # all but the last (current) user message
        messages = build_chat_messages(
            pr_title=p.get("title", ""),
            head_branch=p["head_branch"],
            base_branch=p["base_branch"],
            steps=steps,
            current_step_number=step_number,
            file_patch=file_patch,
            file_source=file_source,
            chat_history=chat_history,
        )

        # Changed files and patches for tools
        changed_files = []
        file_patches_map: dict[str, str] = {}
        try:
            pr_files_list = await provider.list_pull_files(
                _http(request), token, owner, repo, number,
            )
            changed_files = [pf["filename"] for pf in pr_files_list]
            file_patches_map = {
                pf["filename"]: pf.get("patch", "")
                for pf in pr_files_list
                if pf.get("patch")
            }
        except Exception:
            pass

        # Build deps
        deps = ChatDeps(
            provider=provider,
            http_client=_http(request),
            token=token,
            owner=owner,
            repo=repo,
            head_sha=head_sha,
            annotations=annotations_list,
            changed_files=changed_files,
            file_patches=file_patches_map,
        )

        # Build pydantic-ai model
        chat_model = _build_chat_model(cfg.core)

        async def stream_chat():
            from pydantic_ai.usage import UsageLimits as _ChatLimits
            full_content = ""
            try:
                async for event in chat_agent.run_stream_events(
                    user_prompt=message,
                    message_history=messages,
                    model=chat_model,
                    deps=deps,
                    usage_limits=_ChatLimits(request_limit=20),
                ):
                    if isinstance(event, PartStartEvent):
                        if isinstance(event.part, TextPart) and event.part.content:
                            # Add paragraph break between text segments (e.g. after tool calls)
                            if full_content and not full_content.endswith("\n"):
                                full_content += "\n\n"
                                yield _sse("delta", {"content": "\n\n"})
                            full_content += event.part.content
                            yield _sse("delta", {"content": event.part.content})
                    elif isinstance(event, PartDeltaEvent):
                        if isinstance(event.delta, TextPartDelta):
                            delta = event.delta.content_delta
                            full_content += delta
                            yield _sse("delta", {"content": delta})
                    elif isinstance(event, FunctionToolCallEvent):
                        yield _sse("tool_call", {
                            "tool": event.part.tool_name,
                            "args": event.part.args,
                        })
                    elif isinstance(event, FunctionToolResultEvent):
                        # Summarize tool result (first 200 chars)
                        result_content = event.result.content if hasattr(event.result, "content") else ""
                        if isinstance(result_content, str):
                            summary = result_content[:200]
                        else:
                            summary = str(result_content)[:200]
                        yield _sse("tool_result", {
                            "tool": event.result.tool_name if hasattr(event.result, "tool_name") else "",
                            "summary": summary,
                        })

            except Exception as e:
                yield _sse("error", {"message": str(e)})
                return

            # Persist assistant message
            asst_ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            asst_msg = {"role": "assistant", "content": full_content, "timestamp": asst_ts}
            step["chat"].append(asst_msg)

            wf = WalkthroughFile.model_validate(wt_data)
            _get_file_mgr(request, owner, repo).save_walkthrough(wf)

            yield _sse("done", {"message": asst_msg})

        return StreamingResponse(
            stream_chat(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # --- Code Review ---

    async def _load_code_review(request: Request, provider: ForgeProvider, token: str,
                                owner: str, repo: str, branch: str, head_sha: str) -> dict | None:
        """Load code review: forge API → local .specmap/ → user data dir, newest wins."""
        remote_data = None
        sanitized = _safe_branch(branch)
        cr_path = f".specmap/{sanitized}.code-review.json"
        try:
            content = await provider.get_file_content(
                _http(request), token, owner, repo, cr_path, head_sha
            )
            remote_data = json.loads(content)
        except (ForgeNotFound, json.JSONDecodeError, UnicodeDecodeError):
            pass

        local_data = None
        candidates: list[SpecmapFileManager] = []
        if _is_local(request, owner, repo):
            candidates.append(_file_mgr())
        candidates.append(_user_file_mgr(request, owner, repo))

        for mgr in candidates:
            local_cr = mgr.load_code_review(branch)
            if local_cr:
                candidate_data = json.loads(local_cr.model_dump_json())
                if local_data is None:
                    local_data = candidate_data
                elif candidate_data.get("updated_at", "") > local_data.get("updated_at", ""):
                    local_data = candidate_data

        if remote_data and local_data:
            r_time = remote_data.get("updated_at", "")
            l_time = local_data.get("updated_at", "")
            return remote_data if r_time >= l_time else local_data
        return remote_data or local_data

    async def _generate_rich_patches(
        provider: ForgeProvider,
        http_client: httpx.AsyncClient,
        token: str,
        owner: str,
        repo: str,
        file_patches: list[dict],
        head_sha: str,
        base_sha: str,
        context_lines: int = 5,
    ) -> dict[str, str]:
        """Generate unified diffs with configurable context lines.

        Fetches base and head versions of each changed file and produces
        diffs with more context than the 3-line API default.
        """
        from difflib import unified_diff

        result: dict[str, str] = {}
        for fp in file_patches:
            filename = fp["filename"]
            status = fp.get("status", "modified")

            if status == "removed":
                result[filename] = fp.get("patch", "")
                continue

            try:
                head_raw = await provider.get_file_content(
                    http_client, token, owner, repo, filename, head_sha,
                )
                head_lines = head_raw.decode("utf-8", errors="replace").splitlines(keepends=True)
            except ForgeNotFound:
                head_lines = []

            if status == "added":
                base_lines: list[str] = []
            else:
                try:
                    base_raw = await provider.get_file_content(
                        http_client, token, owner, repo, filename, base_sha,
                    )
                    base_lines = base_raw.decode("utf-8", errors="replace").splitlines(keepends=True)
                except ForgeNotFound:
                    base_lines = []

            diff = list(unified_diff(
                base_lines, head_lines,
                fromfile=f"a/{filename}", tofile=f"b/{filename}",
                n=context_lines,
            ))
            if diff:
                result[filename] = "".join(diff)
            else:
                result[filename] = fp.get("patch", "")

        return result

    def _chunk_file_patches(
        file_patches: list[dict],
        threshold: int = 500,
    ) -> list[list[dict]]:
        """Group file patches into chunks by directory, respecting size threshold.

        Returns a list of chunks, where each chunk is a list of file patch dicts.
        If total diff lines are under threshold, returns a single chunk with all files.
        """
        total_lines = sum(fp.get("changes", 0) for fp in file_patches)
        if total_lines <= threshold:
            return [file_patches]

        # Group by top-level directory
        groups: dict[str, list[dict]] = {}
        for fp in file_patches:
            parts = fp["filename"].split("/")
            key = parts[0] if len(parts) > 1 else "__root__"
            groups.setdefault(key, []).append(fp)

        chunks: list[list[dict]] = []
        for group_files in groups.values():
            group_lines = sum(fp.get("changes", 0) for fp in group_files)
            if group_lines <= threshold:
                chunks.append(group_files)
            else:
                current: list[dict] = []
                current_lines = 0
                for fp in group_files:
                    if current_lines + fp.get("changes", 0) > threshold and current:
                        chunks.append(current)
                        current = []
                        current_lines = 0
                    current.append(fp)
                    current_lines += fp.get("changes", 0)
                if current:
                    chunks.append(current)

        return chunks if chunks else [file_patches]

    def _programmatic_dedup(issues: list[dict]) -> list[dict]:
        """Remove exact duplicates: same file + overlapping line ranges."""
        severity_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4}
        kept: list[dict] = []
        for issue in issues:
            is_dup = False
            for existing in kept:
                if (existing["file"] == issue["file"]
                        and existing["start_line"] <= issue.get("end_line", issue["start_line"])
                        and existing.get("end_line", existing["start_line"]) >= issue["start_line"]):
                    # Overlapping — keep higher severity
                    if severity_order.get(issue["severity"], 5) < severity_order.get(existing["severity"], 5):
                        kept.remove(existing)
                        kept.append(issue)
                    is_dup = True
                    break
            if not is_dup:
                kept.append(issue)
        return kept

    async def _handle_generate_code_review(request: Request, owner: str, repo: str, number: int):
        cfg = _cfg(request)
        if not cfg.core.api_key:
            raise HTTPError(503, "LLM not configured. Set SPECMAP_API_KEY.")

        claims = _get_current_user(request)
        token = _get_forge_token(request, claims)
        provider = _provider(request)

        body = await request.json()
        max_issues = body.get("max_issues", 20)
        custom_prompt = body.get("custom_prompt", "")
        context_lines = body.get("context_lines", 5)
        force = body.get("force", False)

        # Fetch PR
        p = await provider.get_pull(_http(request), token, owner, repo, number)
        branch = p["head_branch"]
        head_sha = p["head_sha"]

        # Check existing code review (skip cache if forced or custom prompt provided)
        if not force and not custom_prompt:
            existing_cr = await _load_code_review(
                request, provider, token, owner, repo, branch, head_sha,
            )
            if existing_cr and existing_cr.get("head_sha") == head_sha:
                return existing_cr

        async def _run_two_phase_review(prompt, chunk_patches, model, deps, all_changed_files):
            """Two-phase review: toolless analysis + targeted cross-boundary check."""
            # Phase 1: Toolless review (rescue on failure, returns None if all fails)
            logger.info("Phase 1: toolless review (~%d estimated tokens)", len(prompt) // 4)
            p1_output = await resilient_agent_call(
                review_agent, prompt, model,
                rescue_agent=review_agent,
            )
            p1_issues = []
            summary = ""
            if p1_output is not None:
                summary = p1_output.summary
                for iss in p1_output.issues:
                    p1_issues.append({
                        "issue_number": iss.issue_number,
                        "severity": iss.severity,
                        "title": iss.title,
                        "description": iss.description,
                        "file": iss.file,
                        "start_line": iss.start_line or 0,
                        "end_line": iss.end_line or iss.start_line or 0,
                        "suggested_fix": iss.suggested_fix,
                        "category": iss.category,
                        "reasoning": iss.reasoning,
                    })
                logger.info("Phase 1 found %d issues", len(p1_issues))
            else:
                logger.warning("Phase 1 failed entirely — proceeding with empty issues")

            # Phase 2: Cross-boundary verification (soft limit 10, rescue on failure)
            cb_prompt = build_cross_boundary_prompt(
                chunk_patches=chunk_patches,
                phase1_issues=p1_issues,
                all_changed_files=all_changed_files,
            )
            logger.info("Phase 2: cross-boundary check (~%d estimated tokens)", len(cb_prompt) // 4)
            try:
                p2_output = await resilient_agent_call(
                    cross_boundary_agent, cb_prompt, model,
                    rescue_agent=review_agent,
                    deps=deps,
                    soft_request_limit=10,
                )
                if p2_output is not None:
                    for iss in p2_output.issues:
                        p1_issues.append({
                            "issue_number": len(p1_issues) + 1,
                            "severity": iss.severity,
                            "title": iss.title,
                            "description": iss.description,
                            "file": iss.file,
                            "start_line": iss.start_line or 0,
                            "end_line": iss.end_line or iss.start_line or 0,
                            "suggested_fix": iss.suggested_fix,
                            "category": iss.category,
                            "reasoning": iss.reasoning,
                        })
                    logger.info("Phase 2 found %d additional issues", len(p2_output.issues))
            except Exception as e:
                logger.warning("Phase 2 cross-boundary check failed: %s", e)

            return summary, p1_issues

        async def _stream_review():
            try:
                yield _sse("progress", {"phase": "preparing", "detail": "Loading annotations and file patches..."})

                specmap_data = await _load_annotations(
                    request, provider, token, owner, repo, branch, head_sha,
                )
                annotations_list = specmap_data.get("annotations", []) if specmap_data else []

                file_patches = await provider.list_pull_files(
                    _http(request), token, owner, repo, number,
                )

                spec_files: set[str] = set()
                for ann in annotations_list:
                    for ref in ann.get("refs", []):
                        sf = ref.get("spec_file", "")
                        if sf:
                            spec_files.add(sf)

                spec_contents: dict[str, str] = {}
                for sf in spec_files:
                    try:
                        raw = await provider.get_file_content(
                            _http(request), token, owner, repo, sf, head_sha,
                        )
                        spec_contents[sf] = raw.decode("utf-8", errors="replace")
                    except ForgeNotFound:
                        pass

                # Fetch repo file tree for the prompt
                repo_file_tree: list[str] = []
                try:
                    tree = await provider.list_tree(
                        _http(request), token, owner, repo, head_sha,
                    )
                    repo_file_tree = [e["path"] for e in tree if e["type"] == "blob"]
                except Exception:
                    pass

                base_sha = p.get("base_sha", "")
                changed_files = [fp["filename"] for fp in file_patches]
                file_patches_map = {
                    fp["filename"]: fp.get("patch", "")
                    for fp in file_patches
                    if fp.get("patch")
                }
                chat_model = _build_chat_model(cfg.core)
                chunk_threshold = body.get("chunk_threshold", 500)

                # Pre-load full file content for changed files (avoids read_file tool calls)
                file_contents: dict[str, str] = {}
                for fp in file_patches:
                    fname = fp["filename"]
                    if fp.get("status") == "removed":
                        continue
                    try:
                        raw = await provider.get_file_content(
                            _http(request), token, owner, repo, fname, head_sha,
                        )
                        file_contents[fname] = raw.decode("utf-8", errors="replace")
                    except (ForgeNotFound, Exception):
                        pass

                async def _enrich_patches(patches: list[dict]) -> list[dict]:
                    if not base_sha:
                        return patches
                    rich_map = await _generate_rich_patches(
                        provider, _http(request), token, owner, repo,
                        patches, head_sha, base_sha, context_lines,
                    )
                    result = []
                    for fp in patches:
                        rich_fp = dict(fp)
                        if fp["filename"] in rich_map:
                            rich_fp["patch"] = rich_map[fp["filename"]]
                        result.append(rich_fp)
                    return result

                def _make_deps(chunk_files: list[str], prompt_file_set: set[str] | None = None) -> CodeReviewDeps:
                    return CodeReviewDeps(
                        provider=provider,
                        http_client=_http(request),
                        token=token,
                        owner=owner,
                        repo=repo,
                        head_sha=head_sha,
                        annotations=annotations_list,
                        changed_files=changed_files,
                        file_patches=file_patches_map,
                        prompt_files=prompt_file_set or set(file_contents.keys()),
                    )

                chunks = _chunk_file_patches(file_patches, chunk_threshold)

                def _estimate_tokens(text: str) -> int:
                    return len(text) // 4

                if len(chunks) == 1:
                    yield _sse("progress", {"phase": "reviewing", "detail": "Reviewing PR..."})
                    rich = await _enrich_patches(file_patches)
                    user_prompt = build_code_review_prompt(
                        pr_title=p.get("title", ""),
                        head_branch=p["head_branch"],
                        base_branch=p["base_branch"],
                        annotations=annotations_list,
                        file_patches=rich,
                        spec_contents=spec_contents,
                        max_issues=max_issues,
                        custom_prompt=custom_prompt,
                        file_contents=file_contents,
                        file_tree=repo_file_tree,
                    )
                    logger.info("Code review prompt: ~%d estimated tokens", _estimate_tokens(user_prompt))
                    summary, all_issues = await _run_two_phase_review(
                        user_prompt, file_patches, chat_model,
                        _make_deps(changed_files), changed_files,
                    )
                    # Wrap in a simple namespace for the rest of the pipeline
                    class _ReviewResult:
                        pass
                    review_data = _ReviewResult()
                    review_data.summary = summary
                    review_data.issues = all_issues
                else:
                    n = len(chunks)
                    yield _sse("progress", {"phase": "reviewing", "detail": f"Reviewing {n} chunks (max 4 concurrent)...", "chunk": 0, "total_chunks": n})

                    _chunk_sem = asyncio.Semaphore(4)

                    async def _review_chunk(chunk_patches: list[dict], chunk_idx: int):
                        async with _chunk_sem:
                            rich = await _enrich_patches(chunk_patches)
                            chunk_files_inner = [fp["filename"] for fp in chunk_patches]
                            chunk_ann = [a for a in annotations_list if a.get("file") in chunk_files_inner]
                            chunk_spec_files: set[str] = set()
                            for ann in chunk_ann:
                                for ref in ann.get("refs", []):
                                    sf = ref.get("spec_file", "")
                                    if sf:
                                        chunk_spec_files.add(sf)
                            chunk_specs = {k: v for k, v in spec_contents.items() if k in chunk_spec_files}
                            chunk_contents = {k: v for k, v in file_contents.items() if k in chunk_files_inner}
                            prompt = build_chunk_review_prompt(
                                pr_title=p.get("title", ""),
                                head_branch=p["head_branch"],
                                base_branch=p["base_branch"],
                                chunk_patches=rich,
                                chunk_index=chunk_idx,
                                total_chunks=n,
                                all_changed_files=changed_files,
                                annotations=chunk_ann,
                                spec_contents=chunk_specs,
                                max_issues=max_issues,
                                custom_prompt=custom_prompt,
                                file_contents=chunk_contents,
                                file_tree=repo_file_tree,
                            )
                            logger.info("Chunk %d/%d prompt: ~%d estimated tokens", chunk_idx + 1, n, _estimate_tokens(prompt))
                            summary, issues = await _run_two_phase_review(
                                prompt, chunk_patches, chat_model,
                                _make_deps(chunk_files_inner, prompt_file_set=set(chunk_contents.keys())),
                                changed_files,
                            )
                            return summary, issues

                    chunk_results = await asyncio.gather(
                        *[_review_chunk(chunk, i) for i, chunk in enumerate(chunks)],
                        return_exceptions=True,
                    )

                    all_issues: list[dict] = []
                    chunk_summaries: list[str] = []
                    failed_chunks: list[int] = []
                    for i, result in enumerate(chunk_results):
                        if isinstance(result, BaseException):
                            failed_chunks.append(i + 1)
                            logger.warning("Chunk %d/%d failed: %s", i + 1, n, result)
                            continue
                        summary, issues = result
                        chunk_summaries.append(summary)
                        all_issues.extend(issues)

                    if not chunk_summaries and not all_issues:
                        yield _sse("error", {"message": "All review chunks failed"})
                        return

                    if failed_chunks:
                        chunk_summaries.append(
                            f"Note: Chunks {', '.join(str(c) for c in failed_chunks)} "
                            f"of {n} failed during review and are not included."
                        )

                    deduped = _programmatic_dedup(all_issues)

                    yield _sse("progress", {"phase": "consolidating", "detail": "Validating and consolidating issues..."})
                    consolidation_prompt = build_consolidation_prompt(deduped, chunk_summaries)
                    logger.info("Consolidation prompt: ~%d estimated tokens (%d issues)", _estimate_tokens(consolidation_prompt), len(deduped))
                    review_data = await resilient_agent_call(
                        consolidation_agent, consolidation_prompt, chat_model,
                        rescue_agent=consolidation_agent,
                    )
                    if review_data is None:
                        logger.warning("Consolidation failed — using raw deduped issues")
                        # Create a simple namespace with deduped issues
                        class _FallbackResult:
                            pass
                        review_data = _FallbackResult()
                        review_data.summary = " ".join(chunk_summaries)
                        review_data.issues = deduped

                # Build changed lines set for filtering
                import re as _re
                changed_lines_by_file: dict[str, set[int]] = {}
                for fp in file_patches:
                    lines: set[int] = set()
                    patch = fp.get("patch", "")
                    current_line = 0
                    for pline in patch.splitlines():
                        hunk_match = _re.match(r"^@@ -\\d+(?:,\\d+)? \\+(\\d+)(?:,\\d+)? @@", pline)
                        if hunk_match:
                            current_line = int(hunk_match.group(1))
                            continue
                        if pline.startswith("+") and not pline.startswith("+++"):
                            lines.add(current_line)
                            current_line += 1
                        elif pline.startswith("-") and not pline.startswith("---"):
                            pass
                        else:
                            current_line += 1
                    if fp.get("status") == "added":
                        lines = set(range(1, current_line + 1))
                    changed_lines_by_file[fp["filename"]] = lines

                issues = []
                issue_num = 0
                for issue in review_data.issues:
                    start = issue.start_line or 0 if hasattr(issue, 'start_line') else issue.get("start_line", 0)
                    end = issue.end_line or start if hasattr(issue, 'end_line') else issue.get("end_line", start)
                    file_changed = changed_lines_by_file.get(
                        issue.file if hasattr(issue, 'file') else issue.get("file", ""), set()
                    )
                    if start and not any(line in file_changed for line in range(start, end + 1)):
                        continue
                    issue_num += 1
                    if hasattr(issue, 'severity'):
                        issues.append({
                            "issue_number": issue_num,
                            "severity": issue.severity,
                            "title": issue.title,
                            "description": issue.description,
                            "file": issue.file,
                            "start_line": start,
                            "end_line": end,
                            "suggested_fix": issue.suggested_fix,
                            "category": issue.category,
                            "reasoning": issue.reasoning,
                        })
                    else:
                        issues.append({**issue, "issue_number": issue_num, "start_line": start, "end_line": end})

                cr_data = {
                    "version": 1,
                    "branch": branch,
                    "summary": review_data.summary,
                    "issues": issues,
                    "head_sha": head_sha,
                    "updated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                    "updated_by": "server:generate",
                }

                crf = CodeReviewFile.model_validate(cr_data)
                _get_file_mgr(request, owner, repo).save_code_review(crf)

                yield _sse("complete", cr_data)

            except Exception as e:
                yield _sse("error", {"message": str(e)})

        return StreamingResponse(
            _stream_review(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    async def _handle_dismiss_code_review_issue(request: Request, owner: str, repo: str, number: int):
        claims = _get_current_user(request)
        token = _get_forge_token(request, claims)
        provider = _provider(request)

        body = await request.json()
        issue_number = body.get("issue_number")
        if not issue_number:
            raise HTTPError(400, "issue_number is required")

        p = await provider.get_pull(_http(request), token, owner, repo, number)
        branch = p["head_branch"]
        head_sha = p["head_sha"]

        cr_data = await _load_code_review(
            request, provider, token, owner, repo, branch, head_sha,
        )
        if not cr_data:
            raise HTTPError(404, "No code review found")

        issues = cr_data.get("issues", [])
        issues = [iss for iss in issues if iss.get("issue_number") != issue_number]

        # Renumber remaining issues
        for i, iss in enumerate(issues):
            iss["issue_number"] = i + 1

        cr_data["issues"] = issues
        cr_data["updated_at"] = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )

        crf = CodeReviewFile.model_validate(cr_data)
        _get_file_mgr(request, owner, repo).save_code_review(crf)

        return cr_data

    async def _handle_code_review_chat(request: Request, owner: str, repo: str, number: int):
        cfg = _cfg(request)
        if not cfg.core.api_key:
            raise HTTPError(503, "LLM not configured. Set SPECMAP_API_KEY.")

        claims = _get_current_user(request)
        token = _get_forge_token(request, claims)
        provider = _provider(request)

        body = await request.json()
        issue_number = body.get("issue_number")
        message = body.get("message", "").strip()

        if not issue_number or not message:
            raise HTTPError(400, "issue_number and message are required")

        # Fetch PR info
        p = await provider.get_pull(_http(request), token, owner, repo, number)
        branch = p["head_branch"]
        head_sha = p["head_sha"]

        # Load existing code review
        cr_data = await _load_code_review(
            request, provider, token, owner, repo, branch, head_sha,
        )
        if not cr_data:
            raise HTTPError(404, "No code review found. Generate one first.")

        issues = cr_data.get("issues", [])
        issue_idx = next(
            (i for i, iss in enumerate(issues) if iss.get("issue_number") == issue_number),
            None,
        )
        if issue_idx is None:
            raise HTTPError(404, f"Issue {issue_number} not found")

        issue = issues[issue_idx]

        # Append user message and persist
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        user_msg = {"role": "user", "content": message, "timestamp": now}
        if "chat" not in issue:
            issue["chat"] = []
        issue["chat"].append(user_msg)

        crf = CodeReviewFile.model_validate(cr_data)
        _get_file_mgr(request, owner, repo).save_code_review(crf)

        # Load annotations for context
        specmap_data = await _load_annotations(
            request, provider, token, owner, repo, branch, head_sha,
        )
        annotations_list = specmap_data.get("annotations", []) if specmap_data else []

        # Fetch issue's file patch and source
        file_patch = None
        file_source = None
        issue_file = issue.get("file", "")
        if issue_file:
            try:
                pr_files = await provider.list_pull_files(
                    _http(request), token, owner, repo, number,
                )
                for pf in pr_files:
                    if pf["filename"] == issue_file:
                        file_patch = pf.get("patch", "")
                        break
            except Exception:
                pass

            try:
                raw = await provider.get_file_content(
                    _http(request), token, owner, repo, issue_file, head_sha,
                )
                source_lines = raw.decode("utf-8", errors="replace").splitlines()
                sl = issue.get("start_line", 0)
                el = issue.get("end_line", 0)
                if sl and el:
                    ctx_start = max(sl - 51, 0)
                    ctx_end = min(el + 50, len(source_lines))
                    excerpt = source_lines[ctx_start:ctx_end]
                    numbered = [f"{i}: {line}" for i, line in enumerate(excerpt, ctx_start + 1)]
                    file_source = "\n".join(numbered)
                elif len(source_lines) <= 500:
                    numbered = [f"{i}: {line}" for i, line in enumerate(source_lines, 1)]
                    file_source = "\n".join(numbered)
            except (ForgeNotFound, Exception):
                pass

        # Build chat context — code review issue context instead of walkthrough steps
        from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart as MTextPart, UserPromptPart

        context_parts = [
            "## About This Chat\n"
            "You are helping the user evaluate a code review issue flagged by a separate "
            "AI review agent. The review's claims are NOT ground truth — they may contain "
            "false positives.\n\n"
            "Your job is to independently verify the issue using your tools. When the user "
            "asks about the issue, use read_file and grep_codebase to check the actual code. "
            "If your investigation reveals that the flagged issue is incorrect (e.g., a guard "
            "clause exists that the reviewer missed, or the logic is actually sound), say so "
            "proactively — do not wait for the user to point out the contradiction. "
            "Conclude with a clear assessment: is this a real issue or a false positive?\n",
            f"## PR Overview\n**Title:** {p.get('title', '')}\n**Branch:** {p['head_branch']} → {p['base_branch']}\n",
            f"## Code Review Summary\n{cr_data.get('summary', '')}\n",
            "## All Issues\n",
        ]
        for iss in issues:
            current = " ← CURRENT ISSUE" if iss.get("issue_number") == issue_number else ""
            context_parts.append(
                f"**{iss.get('severity', '?')} #{iss.get('issue_number', '?')}: "
                f"{iss.get('title', '')}** [{iss.get('file', '')}]{current}\n"
                f"{iss.get('description', '')[:200]}...\n"
            )

        context_parts.append("\n## Current Issue Details\n")
        context_parts.append(f"**{issue.get('severity', '')} #{issue_number}: {issue.get('title', '')}**")
        context_parts.append(f"**File:** {issue_file}")
        if issue.get("start_line") and issue.get("end_line"):
            context_parts.append(f"**Lines:** {issue['start_line']}-{issue['end_line']}")
        context_parts.append(f"**Category:** {issue.get('category', '')}")
        context_parts.append(f"**Description:** {issue.get('description', '')}")
        if issue.get("suggested_fix"):
            context_parts.append(f"**Suggested Fix:** {issue['suggested_fix']}")

        if file_patch or file_source:
            context_parts.append("\n## File Context\n")
            if file_patch:
                context_parts.append(f"### Diff\n```diff\n{file_patch}\n```\n")
            if file_source:
                context_parts.append(f"### Source\n```\n{file_source}\n```\n")

        context_text = "\n".join(context_parts)

        messages: list[ModelMessage] = [
            ModelRequest(parts=[UserPromptPart(content=context_text)]),
            ModelResponse(parts=[MTextPart(
                content="I've reviewed the code review context. Feel free to ask about this issue."
            )]),
        ]

        chat_history = issue.get("chat", [])[:-1]
        for msg in chat_history:
            if msg["role"] == "user":
                messages.append(ModelRequest(parts=[UserPromptPart(content=msg["content"])]))
            elif msg["role"] == "assistant":
                messages.append(ModelResponse(parts=[MTextPart(content=msg["content"])]))

        # Build deps and model
        changed_files = []
        file_patches_map: dict[str, str] = {}
        try:
            pr_files_list = await provider.list_pull_files(
                _http(request), token, owner, repo, number,
            )
            changed_files = [pf["filename"] for pf in pr_files_list]
            file_patches_map = {
                pf["filename"]: pf.get("patch", "")
                for pf in pr_files_list if pf.get("patch")
            }
        except Exception:
            pass

        deps = ChatDeps(
            provider=provider,
            http_client=_http(request),
            token=token,
            owner=owner,
            repo=repo,
            head_sha=head_sha,
            annotations=annotations_list,
            changed_files=changed_files,
            file_patches=file_patches_map,
        )

        chat_model = _build_chat_model(cfg.core)

        async def stream_chat():
            from pydantic_ai.usage import UsageLimits as _ChatLimits
            full_content = ""
            try:
                async for event in chat_agent.run_stream_events(
                    user_prompt=message,
                    message_history=messages,
                    model=chat_model,
                    deps=deps,
                    usage_limits=_ChatLimits(request_limit=20),
                ):
                    if isinstance(event, PartStartEvent):
                        if isinstance(event.part, TextPart) and event.part.content:
                            if full_content and not full_content.endswith("\n"):
                                full_content += "\n\n"
                                yield _sse("delta", {"content": "\n\n"})
                            full_content += event.part.content
                            yield _sse("delta", {"content": event.part.content})
                    elif isinstance(event, PartDeltaEvent):
                        if isinstance(event.delta, TextPartDelta):
                            delta = event.delta.content_delta
                            full_content += delta
                            yield _sse("delta", {"content": delta})
                    elif isinstance(event, FunctionToolCallEvent):
                        yield _sse("tool_call", {
                            "tool": event.part.tool_name,
                            "args": event.part.args,
                        })
                    elif isinstance(event, FunctionToolResultEvent):
                        result_content = event.result.content if hasattr(event.result, "content") else ""
                        summary = str(result_content)[:200] if result_content else ""
                        yield _sse("tool_result", {
                            "tool": event.result.tool_name if hasattr(event.result, "tool_name") else "",
                            "summary": summary,
                        })

            except Exception as e:
                yield _sse("error", {"message": str(e)})
                return

            asst_ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            asst_msg = {"role": "assistant", "content": full_content, "timestamp": asst_ts}
            issue["chat"].append(asst_msg)

            crf = CodeReviewFile.model_validate(cr_data)
            _get_file_mgr(request, owner, repo).save_code_review(crf)

            yield _sse("done", {"message": asst_msg})

        return StreamingResponse(
            stream_chat(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # --- Catch-all repo route dispatcher ---
    # Supports nested namespaces (e.g. group/subgroup/project/pulls/42)

    _PULLS_RE = re.compile(
        r"^(?P<full_name>.+)/pulls"
        r"(?:/(?P<number>\d+)(?:/(?P<action>.+))?)?$"
    )

    def _parse_repo_path(repo_path: str) -> tuple[str, str, int | None, str]:
        """Parse repo_path into (owner, name, pr_number|None, sub_action).

        Returns (owner, name, number, action) where action is one of:
        '' (plain repo lookup), 'pulls' (list), 'files', 'file-source',
        'annotations', 'specs/...', 'generate-annotations', 'cache',
        'walkthrough'.
        """
        m = _PULLS_RE.match(repo_path)
        if m:
            full_name = m.group("full_name")
            if "/" not in full_name:
                raise HTTPError(404, "Invalid repo path")
            owner, name = full_name.rsplit("/", 1)
            number_str = m.group("number")
            number = int(number_str) if number_str else None
            action = m.group("action") or ("get" if number_str else "pulls")
            return owner, name, number, action

        # No /pulls — this is a plain repo lookup
        if "/" not in repo_path:
            raise HTTPError(404, "Invalid repo path")
        owner, name = repo_path.rsplit("/", 1)
        return owner, name, None, ""

    @app.api_route("/api/v1/repos/{repo_path:path}", methods=["GET", "POST", "DELETE"])
    async def repo_dispatcher(request: Request, repo_path: str):
        owner, name, number, action = _parse_repo_path(repo_path)
        method = request.method

        # No /pulls in path — repo lookup
        if action == "":
            return await _handle_get_repo(request, owner, name)

        # /pulls with no number — list pulls
        if action == "pulls" and number is None:
            return await _handle_list_pulls(request, owner, name)

        # /pulls/{number} — get single pull
        if action == "get":
            return await _handle_get_pull(request, owner, name, number)
        if action == "files":
            return await _handle_list_pull_files(request, owner, name, number)
        if action == "file-source":
            return await _handle_get_file_source(request, owner, name, number)
        if action == "annotations":
            return await _handle_get_annotations(request, owner, name, number)
        if action == "comments" and method == "GET":
            return await _handle_list_comments(request, owner, name, number)
        if action == "comments" and method == "POST":
            return await _handle_post_comment(request, owner, name, number)
        if action == "generate-annotations" and method == "POST":
            return await _handle_generate_annotations(request, owner, name, number)
        if action == "cache" and method == "DELETE":
            return await _handle_clear_cache(request, owner, name, number)
        if action == "walkthrough" and method == "POST":
            return await _handle_generate_walkthrough(request, owner, name, number)
        if action == "walkthrough/chat" and method == "POST":
            return await _handle_walkthrough_chat(request, owner, name, number)
        if action == "code-review" and method == "POST":
            return await _handle_generate_code_review(request, owner, name, number)
        if action == "code-review/chat" and method == "POST":
            return await _handle_code_review_chat(request, owner, name, number)
        if action == "code-review/dismiss" and method == "POST":
            return await _handle_dismiss_code_review_issue(request, owner, name, number)
        if action.startswith("specs/"):
            spec_path = _safe_spec_path(action[len("specs/"):])
            return await _handle_get_spec_content(request, owner, name, number, spec_path)

        raise HTTPError(404, "Not found")

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
            "provider": u["provider"],
            "provider_id": u["provider_id"],
            "login": u["login"],
            "name": u["name"] or "",
            "avatar_url": u["avatar_url"] or "",
            "created_at": u["created_at"],
            "updated_at": u["updated_at"],
        }

    def _repo_response(r: dict, *, recent_pulls: list[dict] | None = None) -> dict:
        resp = {
            "id": r["id"],
            "provider": r["provider"],
            "provider_id": r["provider_id"],
            "owner": r["owner"],
            "name": r["name"],
            "full_name": r["full_name"],
            "private": bool(r["private"]),
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        if recent_pulls is not None:
            resp["recent_pulls"] = recent_pulls
        return resp

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
        mount_spa(app, config.static_dir)

    return app
