from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .answer import answer_question
from .index import LexicalIndex, strip_accents
from .models import CaseResult, GoldCase

KEYWORD_PASS = 0.5


def load_gold(path: Path) -> list[GoldCase]:
    if not path.exists():
        raise FileNotFoundError(f"gold set no encontrado: {path}")
    cases: list[GoldCase] = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
            cases.append(
                GoldCase(
                    id=str(raw.get("id") or f"q{n:02d}"),
                    question=raw["question"],
                    expected_doc=raw.get("expected_doc"),
                    expected_keywords=list(raw.get("expected_keywords") or []),
                    should_abstain=bool(raw.get("should_abstain", raw.get("expected_doc") is None)),
                )
            )
        except (json.JSONDecodeError, KeyError) as exc:
            raise ValueError(f"{path.name}:{n} inválido: {exc}") from exc
    if not cases:
        raise ValueError(f"{path.name} no tiene casos")
    return cases


def keyword_score(text: str, keywords: list[str]) -> float:
    if not keywords:
        return 1.0
    hay = strip_accents(text)
    found = sum(1 for kw in keywords if strip_accents(kw) in hay)
    return found / len(keywords)


def evaluate_case(index: LexicalIndex, case: GoldCase, k: int) -> CaseResult:
    ans = answer_question(index, case.question, k=k)
    retrieved = list(dict.fromkeys(h.chunk.doc for h in ans.hits))
    cited = list(dict.fromkeys(c.doc for c in ans.citations))
    abstention_ok = ans.abstained == case.should_abstain

    if case.should_abstain:
        recall = citation = True
        kw = 1.0
    else:
        recall = case.expected_doc in retrieved
        citation = (not ans.abstained) and case.expected_doc in cited
        kw = keyword_score(ans.text, case.expected_keywords) if not ans.abstained else 0.0

    passed = abstention_ok and recall and citation and kw >= KEYWORD_PASS
    return CaseResult(
        id=case.id,
        question=case.question,
        expected_doc=case.expected_doc,
        should_abstain=case.should_abstain,
        abstained=ans.abstained,
        confidence=ans.confidence,
        retrieved_docs=retrieved,
        cited_docs=cited,
        recall_hit=recall,
        citation_hit=citation,
        keyword_score=kw,
        abstention_ok=abstention_ok,
        passed=passed,
        answer=ans.text,
    )


def _rate(values: list[bool | float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def compute_metrics(results: list[CaseResult], k: int) -> dict[str, Any]:
    answerable = [r for r in results if not r.should_abstain]
    unanswerable = [r for r in results if r.should_abstain]
    return {
        "cases": len(results),
        "answerable": len(answerable),
        "unanswerable": len(unanswerable),
        "k": k,
        f"recall@{k}": _rate([r.recall_hit for r in answerable]),
        "citation_hit": _rate([r.citation_hit for r in answerable]),
        "keyword_score": _rate([r.keyword_score for r in answerable]),
        "abstention_correct": _rate([r.abstention_ok for r in results]),
        "false_abstain_rate": _rate([r.abstained for r in answerable]),
        "false_answer_rate": _rate([not r.abstained for r in unanswerable]),
        "pass_rate": _rate([r.passed for r in results]),
    }


def run_eval(index: LexicalIndex, gold_path: Path, k: int = 4) -> dict[str, Any]:
    cases = load_gold(gold_path)
    results = [evaluate_case(index, c, k) for c in cases]
    return {
        "gold": gold_path.as_posix(),
        "metrics": compute_metrics(results, k),
        "cases": [r.to_dict() for r in results],
    }


def render_markdown(report: dict[str, Any]) -> str:
    m = report["metrics"]
    k = m["k"]

    def answerable_metric(value: float) -> str:
        return f"{value:.2%}" if m["answerable"] else "n/a"

    lines = [
        "# Evaluación del gold set",
        "",
        f"Gold: `{report['gold']}` · k={k} · casos={m['cases']}",
        "",
        "| Métrica | Valor |",
        "|---|---|",
        f"| recall@{k} | {answerable_metric(m[f'recall@{k}'])} |",
        f"| citation hit | {answerable_metric(m['citation_hit'])} |",
        f"| keyword score | {answerable_metric(m['keyword_score'])} |",
        f"| abstención correcta | {m['abstention_correct']:.2%} |",
        f"| falsa abstención | {m['false_abstain_rate']:.2%} |",
        f"| falsa respuesta | {m['false_answer_rate']:.2%} |",
        f"| pass rate | {m['pass_rate']:.2%} |",
        "",
        "## Casos",
        "",
        "| ID | Resultado | Abstuvo | Confianza | Doc esperado | Docs citados |",
        "|---|---|---|---|---|---|",
    ]
    for c in report["cases"]:
        lines.append(
            "| {id} | {res} | {abs} | {conf:.2f} | {exp} | {cited} |".format(
                id=c["id"],
                res="OK" if c["passed"] else "FALLA",
                abs="sí" if c["abstained"] else "no",
                conf=c["confidence"],
                exp=c["expected_doc"] or "—",
                cited=", ".join(c["cited_docs"]) or "—",
            )
        )
    failed = [c for c in report["cases"] if not c["passed"]]
    if failed:
        lines += ["", "## Fallas", ""]
        for c in failed:
            lines.append(f"- **{c['id']}** {c['question']} → {c['answer']}")
    lines.append("")
    return "\n".join(lines)
