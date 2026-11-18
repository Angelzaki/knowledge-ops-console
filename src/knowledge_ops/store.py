from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .models import Answer
from .ingest import IngestResult

SCHEMA = """
CREATE TABLE IF NOT EXISTS ingest_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  source TEXT NOT NULL,
  docs INTEGER NOT NULL,
  chunks INTEGER NOT NULL,
  skipped INTEGER NOT NULL,
  duration_ms INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL REFERENCES ingest_runs(id),
  name TEXT NOT NULL,
  path TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  words INTEGER NOT NULL,
  chunks INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS queries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  question TEXT NOT NULL,
  answer TEXT NOT NULL,
  abstained INTEGER NOT NULL,
  confidence REAL NOT NULL,
  reason TEXT NOT NULL,
  top_doc TEXT,
  citations TEXT NOT NULL,
  latency_ms INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS eval_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  gold TEXT NOT NULL,
  k INTEGER NOT NULL,
  metrics TEXT NOT NULL,
  cases TEXT NOT NULL
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def record_ingest(self, result: IngestResult) -> int:
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO ingest_runs (ts, source, docs, chunks, skipped, duration_ms)"
                " VALUES (?,?,?,?,?,?)",
                (
                    now_iso(),
                    result.source,
                    len(result.documents),
                    result.chunk_count,
                    len(result.skipped),
                    result.duration_ms,
                ),
            )
            run_id = int(cur.lastrowid)
            c.executemany(
                "INSERT INTO documents (run_id, name, path, sha256, words, chunks)"
                " VALUES (?,?,?,?,?,?)",
                [
                    (run_id, d.name, d.path, d.sha256, d.words, len(d.chunks))
                    for d in result.documents
                ],
            )
        return run_id

    def record_query(self, answer: Answer, latency_ms: int) -> int:
        top = answer.hits[0].chunk.doc if answer.hits else None
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO queries (ts, question, answer, abstained, confidence, reason,"
                " top_doc, citations, latency_ms) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    now_iso(),
                    answer.question,
                    answer.text,
                    int(answer.abstained),
                    answer.confidence,
                    answer.reason,
                    top,
                    json.dumps([x.to_dict() for x in answer.citations], ensure_ascii=False),
                    latency_ms,
                ),
            )
            return int(cur.lastrowid)

    def record_eval(self, gold: str, k: int, metrics: dict, cases: list[dict]) -> int:
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO eval_runs (ts, gold, k, metrics, cases) VALUES (?,?,?,?,?)",
                (
                    now_iso(),
                    gold,
                    k,
                    json.dumps(metrics, ensure_ascii=False),
                    json.dumps(cases, ensure_ascii=False),
                ),
            )
            return int(cur.lastrowid)

    def last_ingest(self) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM ingest_runs ORDER BY id DESC LIMIT 1").fetchone()
            if not row:
                return None
            data = dict(row)
            data["documents"] = [
                dict(r)
                for r in c.execute(
                    "SELECT name, sha256, words, chunks FROM documents WHERE run_id=? ORDER BY name",
                    (row["id"],),
                )
            ]
            return data

    def ingest_history(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM ingest_runs ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def query_history(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM queries ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["abstained"] = bool(d["abstained"])
            d["citations"] = json.loads(d["citations"])
            out.append(d)
        return out

    def latest_eval(self) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM eval_runs ORDER BY id DESC LIMIT 1").fetchone()
        if not row:
            return None
        d = dict(row)
        d["metrics"] = json.loads(d["metrics"])
        d["cases"] = json.loads(d["cases"])
        return d

    def eval_history(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, ts, gold, k, metrics FROM eval_runs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["metrics"] = json.loads(d["metrics"])
            out.append(d)
        return out

    def query_stats(self) -> dict[str, Any]:
        with self._conn() as c:
            row = c.execute(
                "SELECT COUNT(*) AS n, COALESCE(SUM(abstained),0) AS ab,"
                " COALESCE(AVG(latency_ms),0) AS lat FROM queries"
            ).fetchone()
        return {
            "asks": row["n"],
            "abstentions": int(row["ab"]),
            "avg_latency_ms": round(row["lat"], 1),
        }

    def activity(self, limit: int = 15) -> list[dict[str, Any]]:
        sql = """
            SELECT ts, id, 'ingesta' AS kind,
                   'Ingesta #' || id || ': ' || docs || ' docs, ' || chunks || ' chunks' AS detail,
                   'ok' AS status
              FROM ingest_runs
            UNION ALL
            SELECT ts, id, 'consulta' AS kind, question AS detail,
                   CASE WHEN abstained = 1 THEN 'abstencion' ELSE 'ok' END AS status
              FROM queries
            UNION ALL
            SELECT ts, id, 'evaluacion' AS kind,
                   'Evaluación #' || id || ' (k=' || k || ')' AS detail, 'ok' AS status
              FROM eval_runs
            ORDER BY ts DESC, id DESC
            LIMIT ?
        """
        with self._conn() as c:
            rows = c.execute(sql, (limit,)).fetchall()
        return [{k: r[k] for k in ("ts", "kind", "detail", "status")} for r in rows]

    def counts(self) -> dict[str, int]:
        with self._conn() as c:
            return {
                t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in ("ingest_runs", "queries", "eval_runs")
            }
