from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from .models import Chunk, Document

EXTENSIONS = {".txt", ".md"}
MAX_WORDS = 90
HEADING_RE = re.compile(r"^\d+\.\s+\S")


@dataclass
class IngestResult:
    source: str
    documents: list[Document] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    duration_ms: int = 0

    @property
    def chunk_count(self) -> int:
        return sum(len(d.chunks) for d in self.documents)


def _read(path: Path) -> str:
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"no se pudo decodificar {path.name}")


def split_blocks(text: str) -> list[tuple[str, str]]:
    """Devuelve (sección, párrafo) respetando encabezados numerados."""
    blocks: list[tuple[str, str]] = []
    section = ""
    for raw in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
        para = raw.strip()
        if not para:
            continue
        first, _, rest = para.partition("\n")
        if HEADING_RE.match(first) and len(first.split()) <= 12:
            section = first.strip()
            para = rest.strip()
            if not para:
                continue
        blocks.append((section, para))
    return blocks


def chunk_document(name: str, text: str, max_words: int = MAX_WORDS) -> list[Chunk]:
    chunks: list[Chunk] = []
    buf: list[str] = []
    buf_section = ""
    words = 0

    def flush() -> None:
        nonlocal buf, words
        if not buf:
            return
        chunks.append(
            Chunk(
                id=f"{name}#{len(chunks) + 1}",
                doc=name,
                section=buf_section,
                text="\n".join(buf),
                position=len(chunks),
            )
        )
        buf, words = [], 0

    for section, para in split_blocks(text):
        n = len(para.split())
        if buf and (section != buf_section or words + n > max_words):
            flush()
        if not buf:
            buf_section = section
        buf.append(para)
        words += n
    flush()
    return chunks


def load_document(path: Path) -> Document:
    text = _read(path)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    doc = Document(
        name=path.name,
        path=str(path),
        sha256=digest,
        words=len(text.split()),
    )
    doc.chunks = chunk_document(path.name, text)
    return doc


def ingest_dir(source: str | Path) -> IngestResult:
    root = Path(source)
    if not root.is_dir():
        raise FileNotFoundError(f"directorio no encontrado: {root}")
    started = time.perf_counter()
    result = IngestResult(source=str(root.resolve()))
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in EXTENSIONS:
            result.skipped.append(path.name)
            continue
        doc = load_document(path)
        if not doc.chunks:
            result.skipped.append(path.name)
            continue
        result.documents.append(doc)
    result.duration_ms = int((time.perf_counter() - started) * 1000)
    return result
