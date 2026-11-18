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


MAIN_GOLD_STEM = "questions"


def report_basename(gold: str | Path) -> str:
    """El gold principal conserva `eval`; los demás escriben `eval_<nombre>` y no pisan su reporte."""
    stem = Path(gold).stem
    return "eval" if stem == MAIN_GOLD_STEM else f"eval_{stem}"


def write_reports(settings: Settings, report: dict[str, Any], name: str = "eval") -> dict[str, str]:
    settings.results_dir.mkdir(parents=True, exist_ok=True)
    md = settings.results_dir / f"{name}.md"
    js = settings.results_dir / f"{name}.json"
    md.write_text(render_markdown(report), encoding="utf-8")
    js.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"md": str(md), "json": str(js)}


def run_eval_suite(settings: Settings, gold: str | Path, k: int = 4) -> dict[str, Any]:
    settings.ensure_dirs()
    index = LexicalIndex.load(settings.index_path)
    report = run_eval(index, Path(gold), k=k)
    Store(settings.db_path).record_eval(str(gold), k, report["metrics"], report["cases"])
    report["outputs"] = write_reports(settings, report, report_basename(gold))
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
        out["activity"] = store.activity()
        qs = store.query_stats()
    else:
        out["counts"] = {"ingest_runs": 0, "queries": 0, "eval_runs": 0}
        out["last_ingest"] = None
        out["last_eval"] = None
        out["activity"] = []
        qs = {"asks": 0, "abstentions": 0, "avg_latency_ms": 0.0}
    idx = out["index"]
    out["kpis"] = {
        "docs_indexed": idx["docs"] if idx else 0,
        "chunks_indexed": idx["chunks"] if idx else 0,
        "gold_accuracy": out["last_eval"]["metrics"]["pass_rate"] if out["last_eval"] else None,
        **qs,
    }
    return out
