from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .answer import answer_question
from .eval_runner import render_markdown, run_eval
from .index import LexicalIndex
from .ingest import ingest_dir
from .models import Answer, Settings
from .store import Store


def run_ingest(settings: Settings, source: str | Path) -> dict[str, Any]:
    settings.ensure_dirs()
    result = ingest_dir(source)
    if not result.documents:
        raise ValueError(f"no hay documentos .txt/.md válidos en {source}")
    index = LexicalIndex.build([c for d in result.documents for c in d.chunks])
    index.save(settings.index_path)
    run_id = Store(settings.db_path).record_ingest(result)
    return {
        "run_id": run_id,
        "source": result.source,
        "docs": len(result.documents),
        "chunks": result.chunk_count,
        "terms": len(index.idf),
        "skipped": result.skipped,
        "duration_ms": result.duration_ms,
    }


def run_ask(settings: Settings, question: str, k: int = 4) -> Answer:
    settings.ensure_dirs()
    index = LexicalIndex.load(settings.index_path)
    started = time.perf_counter()
    answer = answer_question(index, question, k=k)
    latency = int((time.perf_counter() - started) * 1000)
    Store(settings.db_path).record_query(answer, latency)
    return answer


def write_reports(settings: Settings, report: dict[str, Any]) -> dict[str, str]:
    settings.results_dir.mkdir(parents=True, exist_ok=True)
    md = settings.results_dir / "eval.md"
    js = settings.results_dir / "eval.json"
    md.write_text(render_markdown(report), encoding="utf-8")
    js.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"md": str(md), "json": str(js)}


def run_eval_suite(settings: Settings, gold: str | Path, k: int = 4) -> dict[str, Any]:
    settings.ensure_dirs()
    index = LexicalIndex.load(settings.index_path)
    report = run_eval(index, Path(gold), k=k)
    Store(settings.db_path).record_eval(str(gold), k, report["metrics"], report["cases"])
    report["outputs"] = write_reports(settings, report)
    return report


def status(settings: Settings) -> dict[str, Any]:
    out: dict[str, Any] = {"root": str(settings.root), "index": None}
    if settings.index_path.exists():
        out["index"] = LexicalIndex.load(settings.index_path).stats()
    if settings.db_path.exists():
        store = Store(settings.db_path)
        out["counts"] = store.counts()
        out["last_ingest"] = store.last_ingest()
        ev = store.latest_eval()
        out["last_eval"] = {"ts": ev["ts"], "k": ev["k"], "metrics": ev["metrics"]} if ev else None
    else:
        out["counts"] = {"ingest_runs": 0, "queries": 0, "eval_runs": 0}
        out["last_ingest"] = None
        out["last_eval"] = None
    return out
