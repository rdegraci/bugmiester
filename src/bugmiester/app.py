"""HTTP app / routes (FastAPI)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from bugmiester.analyze import analyze, get_summary
from bugmiester.config import Settings, default_examples_dir, load_settings
from bugmiester.models import (
    NextBugRequest,
    RecoverRequest,
    ReportSnippetRequest,
    SubmitRequest,
)
from bugmiester.reports import list_reports, load_report
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
        "prefetch_next_bug": bool(settings.resilience.prefetch_next_bug),
        "mix": settings.game.mix,
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
            data = store.submit(
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
        for key in ("bug_summary", "bug_category", "hints", "keywords"):
            data.pop(key, None)
        for option in data.get("recovery_options") or []:
            if isinstance(option, dict):
                option.pop("correct", None)
        return data

    @app.post("/api/round/recover")
    def api_round_recover(body: RecoverRequest) -> dict:
        current = _current_settings(app)
        store: RoundStore = app.state.rounds
        try:
            data = store.recover(
                body.round_id,
                body.snippet_id,
                body.option_id,
                current,
            ).model_dump()
        except RoundError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={"message": exc.message, "code": exc.code},
            ) from exc
        for key in ("bug_summary", "bug_category", "hints", "keywords"):
            data.pop(key, None)
        for option in data.get("recovery_options") or []:
            if isinstance(option, dict):
                option.pop("correct", None)
        return data

    @app.post("/api/round/report-snippet")
    def api_round_report_snippet(body: ReportSnippetRequest) -> dict:
        current = _current_settings(app)
        store: RoundStore = app.state.rounds
        try:
            return store.report_snippet(
                body.round_id,
                body.snippet_id,
                body.reason,
                body.note,
                current,
            ).model_dump()
        except RoundError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={"message": exc.message, "code": exc.code},
            ) from exc

    @app.get("/api/round/{round_id}")
    def api_round_resume(
        round_id: str, snippet_id: str | None = Query(default=None)
    ) -> dict:
        store: RoundStore = app.state.rounds
        try:
            data = store.resume(round_id, snippet_id).model_dump()
        except RoundError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={"message": exc.message, "code": exc.code},
            ) from exc
        for key in ("bug_summary", "bug_category", "hints", "keywords"):
            data.pop(key, None)
        for option in data.get("recovery_options") or []:
            if isinstance(option, dict):
                option.pop("correct", None)
        pending = data.get("pending")
        if isinstance(pending, dict):
            for key in ("bug_summary", "bug_category", "hints", "keywords"):
                pending.pop(key, None)
        return data

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

    @app.get("/api/ops/summary")
    def api_ops_summary() -> dict:
        current = _current_settings(app)
        return get_summary(
            current.reports_dir,
            current.logs_dir,
            analyze_on_miss=True,
            persist_on_miss=current.feedback.analyze_on_ops_load,
        )

    @app.post("/api/ops/analyze")
    def api_ops_analyze() -> dict:
        current = _current_settings(app)
        return analyze(
            current.reports_dir,
            current.logs_dir,
            persist=True,
        )

    @app.get("/api/ops/reports")
    def api_ops_reports(
        limit: int = Query(default=50, ge=1, le=500),
        reason: str | None = Query(default=None),
    ) -> list:
        current = _current_settings(app)
        try:
            return list_reports(
                current.reports_dir, limit=limit, reason=reason
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail={"message": str(exc), "code": "invalid_reason"},
            ) from exc

    @app.get("/api/ops/reports/{report_id}")
    def api_ops_report_detail(report_id: str) -> dict:
        current = _current_settings(app)
        payload = load_report(current.reports_dir, report_id)
        if payload is None:
            raise HTTPException(
                status_code=404,
                detail={"message": "Unknown report_id", "code": "unknown_report"},
            )
        return payload

    @app.get("/")
    def game_index() -> FileResponse:
        return FileResponse(
            static_root / "index.html",
            headers={"Cache-Control": "no-store"},
        )

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
