from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from . import service
from .models import Settings
from .store import Store

TEMPLATE = Path(__file__).parent / "templates" / "index.html"


class IngestBody(BaseModel):
    path: str = Field(min_length=1)


class AskBody(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    k: int = Field(default=4, ge=1, le=10)


class EvalBody(BaseModel):
    gold: str = "samples/gold/questions.jsonl"
    k: int = Field(default=4, ge=1, le=10)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(title="Knowledge Ops Console", version="0.1.0")

    def store() -> Store:
        settings.ensure_dirs()
        return Store(settings.db_path)

    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        return TEMPLATE.read_text(encoding="utf-8")

    @app.get("/api/status")
    def api_status():
        return service.status(settings)

    @app.get("/api/ingest/history")
    def api_ingest_history():
        return store().ingest_history()

    @app.post("/api/ingest")
    def api_ingest(body: IngestBody):
        try:
            return service.run_ingest(settings, body.path)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/ask")
    def api_ask(body: AskBody):
        try:
            return service.run_ask(settings, body.question, k=body.k).to_dict()
        except FileNotFoundError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/eval")
    def api_eval(body: EvalBody):
        try:
            return service.run_eval_suite(settings, body.gold, k=body.k)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/eval/latest")
    def api_eval_latest():
        return {"latest": store().latest_eval(), "history": store().eval_history()}

    @app.get("/api/history")
    def api_history(limit: int = 50):
        return store().query_history(limit=max(1, min(limit, 200)))

    return app
