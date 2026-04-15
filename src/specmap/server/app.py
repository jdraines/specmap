"""FastAPI application — all API routes."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from specmap import __version__
from specmap.server import auth
from specmap.server.config import ServerConfig
from specmap.server.db import Database
from specmap.server.forge import (
    ForgeNotFound,
    ForgeProvider,
    detect_auth_mode,
    detect_forge,
    resolve_token,
)
from specmap.server.github import GitHubProvider

logger = logging.getLogger("specmap.server")


def _build_provider(provider_name: str, base_url: str, config: ServerConfig) -> ForgeProvider:
    if provider_name == "gitlab":
        from specmap.server.gitlab import GitLabProvider

        return GitLabProvider(base_url)
    # Default: GitHub (including GHE)
    if base_url != "https://api.github.com":
        return GitHubProvider(base_url)
    return GitHubProvider()


def create_app(config: ServerConfig) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db = Database(config.database_path)
        db.initialize()
        app.state.db = db
        app.state.config = config

        # Auto-detect forge
        provider_name, base_url = detect_forge()
        provider = _build_provider(provider_name, base_url, config)
        app.state.provider = provider
        app.state.auth_mode = detect_auth_mode(config, provider_name)

        # PAT mode: resolve token on startup
        app.state.forge_token: str | None = None
        if app.state.auth_mode == "pat":
            app.state.forge_token = resolve_token(provider_name)
            if app.state.forge_token:
                logger.info("PAT resolved for %s", provider_name)
            else:
                logger.warning(
                    "PAT mode but no token found for %s — set %s or use the web UI to enter one",
                    provider_name,
                    "GITHUB_TOKEN" if provider_name == "github" else "GITLAB_TOKEN",
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
                }
        except HTTPError:
            pass

        # Not authenticated
        hint = ""
        if mode == "pat":
            env_var = "GITHUB_TOKEN" if provider.name == "github" else "GITLAB_TOKEN"
            cli_cmd = "gh auth token" if provider.name == "github" else "glab config get token"
            hint = f"Set {env_var} or run `{cli_cmd}`, then restart the server. Or enter a token below."
        return {
            "authenticated": False,
            "auth_mode": mode,
            "provider": provider.name,
            "setup_hint": hint,
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
        except Exception:
            raise HTTPError(400, "Invalid token — could not authenticate with forge")

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
        has_llm = bool(cfg.llm_api_key)
        return {"walkthrough": has_llm, "annotations": has_llm}

    # --- Data routes ---

    @app.get("/api/v1/repos")
    async def list_repos(request: Request):
        claims = _get_current_user(request)
        token = _get_forge_token(request, claims)
        provider = _provider(request)
        http = _http(request)
        db = _db(request)
        repo_list = await provider.list_repos(http, token)

        # Upsert all repos into DB
        db_repos = []
        for r in repo_list:
            db_repo = db.upsert_repo(
                provider=provider.name,
                provider_id=r["id"],
                owner=r["owner"],
                name=r["name"],
                full_name=r["full_name"],
                private=r["private"],
            )
            db_repos.append(db_repo)

        # Fetch recent PRs for all repos in parallel
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

        result = []
        for db_repo, pulls in zip(db_repos, pulls_per_repo):
            recent = [_pull_response(
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
            ) for p in pulls]
            result.append(_repo_response(db_repo, recent_pulls=recent))

        # Sort repos by most recent PR updated_at (descending)
        def _latest_pull_ts(repo: dict) -> str:
            pulls = repo.get("recent_pulls") or []
            if not pulls:
                return ""
            return max(p["updated_at"] for p in pulls)

        result.sort(key=_latest_pull_ts, reverse=True)
        return result

    @app.get("/api/v1/repos/{owner}/{repo}")
    async def get_repo(request: Request, owner: str, repo: str):
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

    @app.get("/api/v1/repos/{owner}/{repo}/pulls")
    async def list_pulls(request: Request, owner: str, repo: str):
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
        pulls = await provider.list_pulls(_http(request), token, owner, repo)
        result = []
        for p in pulls:
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
        return result

    @app.get("/api/v1/repos/{owner}/{repo}/pulls/{number}")
    async def get_pull(request: Request, owner: str, repo: str, number: int):
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

    @app.get("/api/v1/repos/{owner}/{repo}/pulls/{number}/files")
    async def list_pull_files(request: Request, owner: str, repo: str, number: int):
        claims = _get_current_user(request)
        token = _get_forge_token(request, claims)
        provider = _provider(request)
        return await provider.list_pull_files(_http(request), token, owner, repo, number)

    @app.get("/api/v1/repos/{owner}/{repo}/pulls/{number}/file-source")
    async def get_file_source(request: Request, owner: str, repo: str, number: int):
        claims = _get_current_user(request)
        token = _get_forge_token(request, claims)
        provider = _provider(request)
        path = request.query_params.get("path", "")
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

    @app.get("/api/v1/repos/{owner}/{repo}/pulls/{number}/annotations")
    async def get_annotations(request: Request, owner: str, repo: str, number: int):
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

        head_sha = db_pull["head_sha"]

        cached = db.get_mapping_cache(db_pull["id"], head_sha)
        if cached:
            return json.loads(cached)

        branch = db_pull["head_branch"]
        sanitized = branch.replace("/", "--")
        specmap_path = f".specmap/{sanitized}.json"

        try:
            content = await provider.get_file_content(
                _http(request), token, owner, repo, specmap_path, head_sha
            )
            specmap_data = json.loads(content)
        except ForgeNotFound:
            specmap_data = _empty_specmap(branch, db_pull)
        except (json.JSONDecodeError, UnicodeDecodeError):
            specmap_data = _empty_specmap(branch, db_pull)

        db.upsert_mapping_cache(db_pull["id"], head_sha, json.dumps(specmap_data))

        return specmap_data

    @app.get("/api/v1/repos/{owner}/{repo}/pulls/{number}/specs/{path:path}")
    async def get_spec_content(request: Request, owner: str, repo: str, number: int, path: str):
        claims = _get_current_user(request)
        token = _get_forge_token(request, claims)
        provider = _provider(request)
        p = await provider.get_pull(_http(request), token, owner, repo, number)
        head_sha = p["head_sha"]
        try:
            content = await provider.get_file_content(
                _http(request), token, owner, repo, path, head_sha
            )
            return {"path": path, "content": content.decode("utf-8", errors="replace")}
        except ForgeNotFound:
            raise HTTPError(404, "Spec file not found")

    # --- Generate Annotations ---

    @app.post("/api/v1/repos/{owner}/{repo}/pulls/{number}/generate-annotations")
    async def generate_annotations(request: Request, owner: str, repo: str, number: int):
        cfg = _cfg(request)
        if not cfg.llm_api_key:
            raise HTTPError(503, "LLM not configured. Set SPECMAP_API_KEY.")

        claims = _get_current_user(request)
        token = _get_forge_token(request, claims)
        provider = _provider(request)
        db = _db(request)

        body = await request.json()
        mode = body.get("mode", "full")
        force = body.get("force", False)

        if mode not in ("lite", "full"):
            raise HTTPError(400, 'mode must be "lite" or "full"')

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

        # Check cache
        if not force:
            cached = db.get_mapping_cache(db_pull["id"], head_sha)
            if cached:
                cached_data = json.loads(cached)
                if cached_data.get("annotations"):
                    return cached_data

        # Fetch PR files
        pr_files = await provider.list_pull_files(
            _http(request), token, owner, repo, number
        )

        # Generate
        from specmap.server.generate import generate_full, generate_lite

        if mode == "lite":
            specmap_data = await generate_lite(
                provider, _http(request), token,
                owner, repo, pr_files,
                head_sha, db_pull["head_branch"], db_pull["base_branch"],
                cfg.llm_model, cfg.llm_api_key, cfg.llm_api_base,
            )
        else:
            specmap_data = await generate_full(
                provider, _http(request), token,
                owner, repo, pr_files,
                head_sha, db_pull["head_branch"], db_pull["base_branch"],
                cfg.llm_model, cfg.llm_api_key, cfg.llm_api_base,
                pr_title=db_pull["title"],
            )

        # Cache and return
        db.upsert_mapping_cache(db_pull["id"], head_sha, json.dumps(specmap_data))
        return specmap_data

    # --- Walkthrough ---

    @app.post("/api/v1/repos/{owner}/{repo}/pulls/{number}/walkthrough")
    async def generate_walkthrough(request: Request, owner: str, repo: str, number: int):
        cfg = _cfg(request)
        if not cfg.llm_api_key:
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
        head_sha = db_pull["head_sha"]

        # Check cache
        cached = db.get_walkthrough_cache(db_pull["id"], head_sha, familiarity, depth)
        if cached:
            return json.loads(cached)

        # Get annotations
        ann_cached = db.get_mapping_cache(db_pull["id"], head_sha)
        if ann_cached:
            specmap_data = json.loads(ann_cached)
        else:
            branch = db_pull["head_branch"]
            sanitized = branch.replace("/", "--")
            specmap_path = f".specmap/{sanitized}.json"
            try:
                content = await provider.get_file_content(
                    _http(request), token, owner, repo, specmap_path, head_sha
                )
                specmap_data = json.loads(content)
            except (ForgeNotFound, json.JSONDecodeError, UnicodeDecodeError):
                specmap_data = _empty_specmap(branch, db_pull)
            db.upsert_mapping_cache(db_pull["id"], head_sha, json.dumps(specmap_data))

        annotations_list = specmap_data.get("annotations", [])
        if not annotations_list:
            # Auto-generate annotations via full mode
            try:
                pr_files_for_gen = await provider.list_pull_files(
                    _http(request), token, owner, repo, number
                )
                from specmap.server.generate import generate_full, generate_lite

                try:
                    specmap_data = await generate_full(
                        provider, _http(request), token,
                        owner, repo, pr_files_for_gen,
                        head_sha, db_pull["head_branch"], db_pull["base_branch"],
                        cfg.llm_model, cfg.llm_api_key, cfg.llm_api_base,
                        pr_title=db_pull["title"],
                    )
                except Exception:
                    # Fallback to lite mode
                    specmap_data = await generate_lite(
                        provider, _http(request), token,
                        owner, repo, pr_files_for_gen,
                        head_sha, db_pull["head_branch"], db_pull["base_branch"],
                        cfg.llm_model, cfg.llm_api_key, cfg.llm_api_base,
                    )
                db.upsert_mapping_cache(
                    db_pull["id"], head_sha, json.dumps(specmap_data)
                )
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
        from specmap.config import SpecmapConfig as CoreConfig
        from specmap.llm.client import LLMClient
        from specmap.llm.walkthrough_prompts import build_walkthrough_prompt
        from specmap.llm.walkthrough_schemas import WalkthroughResponse

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

        llm_config = CoreConfig(
            model=cfg.llm_model,
            api_key=cfg.llm_api_key,
            api_base=cfg.llm_api_base or None,
        )
        llm_client = LLMClient(llm_config)
        result = await llm_client.complete(messages, response_format=WalkthroughResponse)

        # Build response
        import datetime

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
                "start_line": step.start_line,
                "end_line": step.end_line,
                "refs": refs,
            })

        walkthrough_data = {
            "summary": result.summary,
            "steps": steps,
            "familiarity": familiarity,
            "depth": depth,
            "head_sha": head_sha,
            "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
        }

        # Cache and return
        db.upsert_walkthrough_cache(
            db_pull["id"], head_sha, familiarity, depth, json.dumps(walkthrough_data)
        )
        return walkthrough_data

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
        from specmap.server.spa import mount_spa

        mount_spa(app, config.static_dir)

    return app
