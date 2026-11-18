from __future__ import annotations

import json
from pathlib import Path

import pytest

from knowledge_ops import service
from knowledge_ops.cli import main
from knowledge_ops.index import LexicalIndex, tokenize
from knowledge_ops.ingest import chunk_document
from knowledge_ops.models import Settings
from knowledge_ops.store import Store

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "samples" / "docs"
GOLD = ROOT / "samples" / "gold" / "questions.jsonl"


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    return Settings.from_env(tmp_path)


@pytest.fixture()
def ingested(settings: Settings) -> Settings:
    service.run_ingest(settings, DOCS)
    return settings


def test_tokenize_strips_accents_and_stopwords():
    toks = tokenize("¿Cuántos días de reembolso?")
    assert len(toks) == 2
    assert toks == tokenize("dia reembolsos")
    assert "de" not in toks


def test_chunking_keeps_sections():
    text = "1. Alcance\nAplica a todos.\n\n2. Plazo\nSon 15 días calendario."
    chunks = chunk_document("x.txt", text)
    assert [c.section for c in chunks] == ["1. Alcance", "2. Plazo"]
    assert chunks[1].id == "x.txt#2"


def test_ingest_builds_index_and_metadata(settings: Settings):
    r = service.run_ingest(settings, DOCS)
    assert r["docs"] == 4
    assert r["chunks"] >= 20
    assert settings.index_path.exists()
    idx = LexicalIndex.load(settings.index_path)
    assert idx.n == r["chunks"]
    last = Store(settings.db_path).last_ingest()
    assert last and last["docs"] == 4 and len(last["documents"]) == 4


def test_ingest_missing_dir(settings: Settings, tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        service.run_ingest(settings, tmp_path / "nada")


def test_ask_returns_cited_answer(ingested: Settings):
    ans = service.run_ask(ingested, "¿Cuál es la longitud mínima de una contraseña?")
    assert not ans.abstained
    assert "12 caracteres" in ans.text
    assert ans.citations[0].doc == "politica_accesos.txt"
    assert ans.confidence >= 0.4


def test_ask_abstains_without_evidence(ingested: Settings):
    ans = service.run_ask(ingested, "¿Cuál es el precio actual del bitcoin en dólares?")
    assert ans.abstained
    assert ans.citations == []


def test_queries_are_logged(ingested: Settings):
    service.run_ask(ingested, "¿En cuánto tiempo se responde un incidente de severidad 1?")
    service.run_ask(ingested, "¿Quién ganó el mundial de fútbol de 2018?")
    hist = Store(ingested.db_path).query_history()
    assert len(hist) == 2
    assert {h["abstained"] for h in hist} == {True, False}


def test_eval_happy_path_writes_reports(ingested: Settings):
    report = service.run_eval_suite(ingested, GOLD, k=4)
    m = report["metrics"]
    assert m["cases"] >= 8
    assert m["recall@4"] == 1.0
    assert m["citation_hit"] >= 0.9
    assert m["abstention_correct"] == 1.0
    assert m["pass_rate"] >= 0.9

    md = Path(report["outputs"]["md"])
    js = Path(report["outputs"]["json"])
    assert md.exists() and "recall@4" in md.read_text(encoding="utf-8")
    assert json.loads(js.read_text(encoding="utf-8"))["metrics"]["cases"] == m["cases"]
    assert Store(ingested.db_path).latest_eval()["metrics"]["cases"] == m["cases"]


def test_status_kpis_and_activity(settings: Settings):
    empty = service.status(settings)["kpis"]
    assert empty["docs_indexed"] == 0 and empty["gold_accuracy"] is None and empty["asks"] == 0

    service.run_ingest(settings, DOCS)
    service.run_ask(settings, "¿Cuál es la longitud mínima de una contraseña?")
    service.run_ask(settings, "¿Quién ganó el mundial de fútbol de 2018?")
    service.run_eval_suite(settings, GOLD, k=4)

    st = service.status(settings)
    k = st["kpis"]
    assert k["docs_indexed"] == 4
    assert k["asks"] == 2 and k["abstentions"] == 1
    assert k["gold_accuracy"] == 1.0
    kinds = {a["kind"] for a in st["activity"]}
    assert kinds == {"ingesta", "consulta", "evaluacion"}
    assert any(a["status"] == "abstencion" for a in st["activity"])


def test_cli_end_to_end(tmp_path: Path, capsys):
    home = str(tmp_path)
    assert main(["--home", home, "ingest", str(DOCS)]) == 0
    assert main(["--home", home, "ask", "¿Cuántos días de vacaciones corresponden por año?"]) == 0
    assert main(["--home", home, "eval", "--gold", str(GOLD)]) == 0
    assert main(["--home", home, "status"]) == 0
    out = capsys.readouterr().out
    assert "RESPUESTA" in out
    assert "consultas=1" in out


def test_cli_ask_without_index_fails_cleanly(tmp_path: Path, capsys):
    assert main(["--home", str(tmp_path), "ask", "hola"]) == 2
    assert "ingest" in capsys.readouterr().err


def test_web_flow(settings: Settings):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from knowledge_ops.web import create_app

    client = TestClient(create_app(settings))
    assert "Knowledge Ops Console" in client.get("/").text
    assert client.post("/api/ask", json={"question": "¿hola mundo?"}).status_code == 409
    assert client.post("/api/ingest", json={"path": str(DOCS)}).json()["docs"] == 4
    ans = client.post("/api/ask", json={"question": "¿Cuánto es el bono mensual de internet?"}).json()
    assert not ans["abstained"] and ans["citations"]
    ev = client.post("/api/eval", json={"gold": str(GOLD)}).json()
    assert ev["metrics"]["pass_rate"] >= 0.9
    assert len(client.get("/api/history").json()) == 1
    assert client.get("/api/status").json()["counts"]["eval_runs"] == 1
