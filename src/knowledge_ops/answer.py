from __future__ import annotations

import re

from .index import LexicalIndex, tokenize
from .models import Answer, Citation, Hit
from .retrieve import query_terms, search

MIN_COVERAGE = 0.45
MIN_CONFIDENCE = 0.40
MAX_SENTENCES = 2
SNIPPET_CHARS = 220
ABSTAIN_TEXT = "No hay evidencia suficiente en los documentos indexados. Escale a una persona."


def split_sentences(text: str) -> list[str]:
    out: list[str] = []
    for line in text.splitlines():
        for part in re.split(r"(?<=[.;])\s+", line.strip()):
            part = part.strip()
            if len(part) > 12:
                out.append(part)
    return out


def confidence_of(top: Hit, second: Hit | None) -> float:
    strength = min(1.0, top.score / 0.35)
    margin = 0.0
    if second is None:
        margin = 1.0
    elif top.score > 0:
        margin = min(1.0, max(0.0, (top.score - second.score) / top.score) * 2)
    return round(0.65 * top.coverage + 0.25 * strength + 0.10 * margin, 4)


def _rank_sentences(index: LexicalIndex, question: str, hit: Hit) -> list[tuple[float, str]]:
    terms = set(query_terms(question))
    ranked: list[tuple[float, str]] = []
    for sent in split_sentences(hit.chunk.text):
        toks = set(tokenize(sent))
        overlap = sum(index.term_idf(t) for t in terms & toks)
        if overlap > 0:
            ranked.append((overlap, sent))
    ranked.sort(key=lambda x: -x[0])
    return ranked


def _snippet(text: str) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= SNIPPET_CHARS else flat[: SNIPPET_CHARS - 1].rstrip() + "…"


def answer_question(
    index: LexicalIndex,
    question: str,
    k: int = 4,
    min_coverage: float = MIN_COVERAGE,
    min_confidence: float = MIN_CONFIDENCE,
) -> Answer:
    hits = search(index, question, k=k)
    if not hits:
        return Answer(question, ABSTAIN_TEXT, True, 0.0, [], "sin coincidencias léxicas", hits)

    top = hits[0]
    confidence = confidence_of(top, hits[1] if len(hits) > 1 else None)
    if top.coverage < min_coverage:
        reason = f"cobertura baja ({top.coverage:.2f} < {min_coverage:.2f})"
        return Answer(question, ABSTAIN_TEXT, True, confidence, [], reason, hits)
    if confidence < min_confidence:
        reason = f"confianza baja ({confidence:.2f} < {min_confidence:.2f})"
        return Answer(question, ABSTAIN_TEXT, True, confidence, [], reason, hits)

    sentences = _rank_sentences(index, question, top)[:MAX_SENTENCES]
    if not sentences:
        return Answer(question, ABSTAIN_TEXT, True, confidence, [], "sin oraciones útiles", hits)

    order = {s: i for i, s in enumerate(split_sentences(top.chunk.text))}
    picked = sorted((s for _, s in sentences), key=lambda s: order.get(s, 0))
    text = " ".join(picked) + " [1]"
    citations = [
        Citation(
            n=1,
            doc=top.chunk.doc,
            chunk_id=top.chunk.id,
            section=top.chunk.section,
            snippet=_snippet(top.chunk.text),
            score=top.score,
        )
    ]

    runner = hits[1] if len(hits) > 1 else None
    if runner and runner.chunk.doc != top.chunk.doc and runner.coverage >= max(
        min_coverage, top.coverage - 0.1
    ):
        extra = _rank_sentences(index, question, runner)[:1]
        if extra:
            text += f" {extra[0][1]} [2]"
            citations.append(
                Citation(
                    n=2,
                    doc=runner.chunk.doc,
                    chunk_id=runner.chunk.id,
                    section=runner.chunk.section,
                    snippet=_snippet(runner.chunk.text),
                    score=runner.score,
                )
            )

    return Answer(question, text, False, confidence, citations, "", hits)
