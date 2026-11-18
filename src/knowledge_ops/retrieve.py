from __future__ import annotations

import math
from collections import Counter

from .index import LexicalIndex, tokenize
from .models import Hit


def query_terms(question: str) -> list[str]:
    return list(dict.fromkeys(tokenize(question)))


def search(index: LexicalIndex, question: str, k: int = 4) -> list[Hit]:
    """TF-IDF coseno; coverage = peso idf de términos de la consulta presentes en el chunk."""
    terms = query_terms(question)
    if not terms:
        return []
    qtf = Counter(tokenize(question))
    qweights = {t: (1 + math.log(qtf[t])) * index.term_idf(t) for t in terms}
    qnorm = math.sqrt(sum(w * w for w in qweights.values())) or 1.0
    total_idf = sum(index.term_idf(t) for t in terms)

    hits: list[Hit] = []
    for chunk in index.chunks:
        ctf = index.tf[chunk.id]
        matched = [t for t in terms if t in ctf]
        if not matched:
            continue
        dot = sum(qweights[t] * (1 + math.log(ctf[t])) * index.idf[t] for t in matched)
        score = dot / (qnorm * index.norms[chunk.id])
        coverage = sum(index.term_idf(t) for t in matched) / total_idf
        hits.append(Hit(chunk=chunk, score=score, coverage=coverage, matched=matched))

    hits.sort(key=lambda h: (-h.score, h.chunk.id))
    return hits[:k]
