from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Settings:
    root: Path

    @classmethod
    def from_env(cls, home: str | Path | None = None) -> "Settings":
        base = home or os.environ.get("KNOPS_HOME") or Path.cwd()
        return cls(root=Path(base).resolve())

    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    @property
    def index_path(self) -> Path:
        return self.data_dir / "index.json"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "knowledge.db"

    @property
    def results_dir(self) -> Path:
        return self.root / "results"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)


@dataclass
class Chunk:
    id: str
    doc: str
    section: str
    text: str
    position: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Document:
    name: str
    path: str
    sha256: str
    words: int
    chunks: list[Chunk] = field(default_factory=list)


@dataclass
class Hit:
    chunk: Chunk
    score: float
    coverage: float
    matched: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk.id,
            "doc": self.chunk.doc,
            "section": self.chunk.section,
            "score": round(self.score, 4),
            "coverage": round(self.coverage, 4),
            "matched": self.matched,
        }


@dataclass
class Citation:
    n: int
    doc: str
    chunk_id: str
    section: str
    snippet: str
    score: float

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["score"] = round(self.score, 4)
        return d


@dataclass
class Answer:
    question: str
    text: str
    abstained: bool
    confidence: float
    citations: list[Citation]
    reason: str = ""
    hits: list[Hit] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.text,
            "abstained": self.abstained,
            "confidence": round(self.confidence, 4),
            "reason": self.reason,
            "citations": [c.to_dict() for c in self.citations],
            "hits": [h.to_dict() for h in self.hits],
        }


@dataclass
class GoldCase:
    id: str
    question: str
    expected_doc: str | None = None
    expected_keywords: list[str] = field(default_factory=list)
    should_abstain: bool = False


@dataclass
class CaseResult:
    id: str
    question: str
    expected_doc: str | None
    should_abstain: bool
    abstained: bool
    confidence: float
    retrieved_docs: list[str]
    cited_docs: list[str]
    recall_hit: bool
    citation_hit: bool
    keyword_score: float
    abstention_ok: bool
    passed: bool
    answer: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["confidence"] = round(self.confidence, 4)
        d["keyword_score"] = round(self.keyword_score, 4)
        return d
