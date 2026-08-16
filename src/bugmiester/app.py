"""HTTP app / routes (FastAPI)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from bugmiester.config import Settings, default_examples_dir, load_settings
from bugmiester.models import NextBugRequest, SubmitRequest
from bugmiester.rounds import RoundError, RoundStore


def web_dir() -> Path:
    """Repo `web/` directory (editable / source checkout)."""
    return Path(__file__).resolve().parents[2] / "web"


def health_payload(settings: Settings) -> dict:
    if settings.config_ready:
        message = f"Ready ({settings.llm.provider})"
    elif settings.missing_key:
        message = f"Set {settings.missing_key} in {settings.env_path}"
    else:
        message = f"Configure the selected provider in {settings.env_path}"

    return {
        "ok": True,
        "config_ready": settings.config_ready,
        "provider": settings.llm.provider,
        "app_dir": str(settings.app_dir),
        "env_path": str(settings.env_path),
        "config_path": str(settings.config_path),
        "missing_key": settings.missing_key,
        "message": message,
    }


def _current_settings(app: FastAPI) -> Settings:
    previous: Settings | None = getattr(app.state, "settings", None)
    current = load_settings(
        app_dir=previous.app_dir if previous is not None else None,
        examples_dir=default_examples_dir(),
    )
    app.state.settings = current
    return current


def create_app(settings: Settings | None = None) -> FastAPI:
    """
    Build the FastAPI app.

    Loads Application Support config on startup when settings is omitted.
    """
    static_root = web_dir()
    if not static_root.is_dir():
        raise FileNotFoundError(f"Web UI directory not found: {static_root}")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if settings is not None:
            app.state.settings = settings
        else:
            app.state.settings = load_settings(examples_dir=default_examples_dir())
        app.state.rounds = RoundStore()
        yield

    app = FastAPI(
        title="Bugmiester",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )

    @app.get("/api/health")
    def api_health() -> dict:
        return health_payload(_current_settings(app))

    @app.post("/api/round/start")
    def api_round_start() -> dict:
        current = _current_settings(app)
        store: RoundStore = app.state.rounds
        return store.start(current).model_dump()

    @app.post("/api/round/next-bug")
    def api_round_next_bug(body: NextBugRequest) -> dict:
        current = _current_settings(app)
        store: RoundStore = app.state.rounds
        try:
            payload = store.next_bug(body.round_id, current)
        except RoundError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={"message": exc.message, "code": exc.code},
            ) from exc
        data = payload.model_dump()
        # Belt-and-suspenders: never leak answer-key fields.
        for key in ("bug_summary", "bug_category", "hints", "keywords"):
            data.pop(key, None)
        return data

    @app.post("/api/round/submit")
    def api_round_submit(body: SubmitRequest) -> dict:
        current = _current_settings(app)
        store: RoundStore = app.state.rounds
        try:
            return store.submit(
                body.round_id,
                body.snippet_id,
                body.answer,
                current,
            ).model_dump()
        except RoundError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={"message": exc.message, "code": exc.code},
            ) from exc

    @app.get("/api/round/{round_id}/summary")
    def api_round_summary(round_id: str) -> dict:
        store: RoundStore = app.state.rounds
        try:
            return store.summary(round_id).model_dump()
        except RoundError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={"message": exc.message, "code": exc.code},
            ) from exc

    @app.get("/")
    def game_index() -> FileResponse:
        return FileResponse(static_root / "index.html")

    @app.get("/ops")
    def ops_dashboard() -> FileResponse:
        return FileResponse(static_root / "ops.html")

    # CSS/JS/vendor assets (same-origin). Registered after API/page routes.
    app.mount(
        "/",
        StaticFiles(directory=static_root),
        name="web-static",
    )

    return app


# ASGI entry for uvicorn: `uvicorn bugmiester.app:app`
app = create_app()
