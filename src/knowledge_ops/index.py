from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .models import Chunk

STOPWORDS = frozenset(
    """a al algo ante antes aqui as asi aun cada como con contra cual cuales cuando cuanta cuantas
    cuanto cuantos de del desde donde dos e el ella ellas ello ellos en entre era es esa esas ese eso
    esos esta estan estar este esto estos fue ha hay la las le les lo los mas me mi mis muy ni no nos
    o para pero por porque que quien quienes se sea ser si sin sobre son su sus tambien tan te tengo
    tiene tienen todo tu tus un una uno unos y ya yo""".split()
)

TOKEN_RE = re.compile(r"[a-z0-9]+")
INDEX_VERSION = 1


def strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c)
    )


def stem(token: str) -> str:
    if token.isdigit() or len(token) <= 3:
        return token
    if token.endswith("es") and len(token) > 5:
        token = token[:-2]
    elif token.endswith("s"):
        token = token[:-1]
    if len(token) > 5 and token[-1] in "aeo":
        token = token[:-1]
    return token


def tokenize(text: str) -> list[str]:
    out = []
    for tok in TOKEN_RE.findall(strip_accents(text)):
        if tok in STOPWORDS:
            continue
        out.append(stem(tok))
    return out


class LexicalIndex:
    def __init__(self, chunks: list[Chunk], tf: dict[str, dict[str, int]], built_at: str = ""):
        self.chunks = chunks
        self.tf = tf
        self.built_at = built_at
        self.by_id = {c.id: c for c in chunks}
        self._compute()

    def _compute(self) -> None:
        n = len(self.chunks)
        df: Counter[str] = Counter()
        for terms in self.tf.values():
            df.update(terms.keys())
        self.n = n
        self.df = df
        self.idf = {t: math.log(1 + n / d) + 1.0 for t, d in df.items()}
        self.unknown_idf = math.log(1 + n) + 1.0
        self.norms: dict[str, float] = {}
        for cid, terms in self.tf.items():
            s = sum(((1 + math.log(f)) * self.idf[t]) ** 2 for t, f in terms.items())
            self.norms[cid] = math.sqrt(s) or 1.0

    @classmethod
    def build(cls, chunks: list[Chunk]) -> "LexicalIndex":
        tf: dict[str, dict[str, int]] = {}
        for c in chunks:
            title = c.section if c.section else ""
            tf[c.id] = dict(Counter(tokenize(f"{title} {c.text}")))
        built = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return cls(chunks, tf, built)

    @property
    def docs(self) -> list[str]:
        return sorted({c.doc for c in self.chunks})

    def term_idf(self, term: str) -> float:
        return self.idf.get(term, self.unknown_idf)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": INDEX_VERSION,
            "built_at": self.built_at,
            "chunks": [c.to_dict() for c in self.chunks],
            "tf": self.tf,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "LexicalIndex":
        if not path.exists():
            raise FileNotFoundError(f"índice no encontrado: {path}. Ejecute `ingest` primero.")
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("version") != INDEX_VERSION:
            raise ValueError("versión de índice incompatible; vuelva a ejecutar `ingest`")
        chunks = [Chunk(**c) for c in data["chunks"]]
        return cls(chunks, data["tf"], data.get("built_at", ""))

    def stats(self) -> dict:
        return {
            "docs": len(self.docs),
            "chunks": self.n,
            "terms": len(self.idf),
            "built_at": self.built_at,
        }
