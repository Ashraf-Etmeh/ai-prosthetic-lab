"""Ingestion: source documents -> chunks -> vectors in data/vector_store/.

Run:  python -m knowledge.ingest

1. Extracts the text of every catalogued document (knowledge/extract.py),
   writing data/extracted/<id>.txt.
2. Cuts each document into overlapping chunks of about CHUNK_SIZE_CHARS
   characters, ending at sentence ends, and remembers the page each chunk
   starts and ends on.
3. Turns every chunk into a vector with the embedding model.
4. Saves three files in data/vector_store/:
     vectors.npy  one row per chunk: row 17 belongs to chunk 17 in chunks.json
     chunks.json  each chunk's id, text, page and citation details
     info.json    the model and settings used; retrieval checks it

Run it again whenever a document, the catalog, the cleaning or the model
changes. Chunk ids are "<document id>-<number>", so they stay the same as
long as the document's text and the chunk settings stay the same.
"""

import json
import os
import re
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

from knowledge.catalog import SourceDocument
from knowledge.embedding import embed_texts
from knowledge.extract import Page, extract_all, read_extracted
from shared.config import (
    CATALOG_PATH,
    CHUNK_OVERLAP_CHARS,
    CHUNK_SIZE_CHARS,
    EMBEDDING_MODEL_NAME,
    EMBEDDING_MODEL_REVISION,
    EXTRACTED_DIR,
    SOURCES_DIR,
    VECTOR_STORE_DIR,
)

VECTORS_FILE = "vectors.npy"
CHUNKS_FILE = "chunks.json"
INFO_FILE = "info.json"

# A sentence ends at . ! ? or the Arabic question mark, followed by a space.
_SENTENCE_END = re.compile(r"(?<=[.!?؟])\s+")

Chunk = tuple[int, int, str]  # (first page, last page, text)


# ---- Chunking -----------------------------------------------------------


def split_sentences(pages: list[Page], max_chars: int = CHUNK_SIZE_CHARS) -> list[tuple[int, str]]:
    """(page, sentence) for every sentence, in reading order.

    PDF lines are joined first, since a line break is usually just the edge
    of the page. A "sentence" longer than max_chars (a table or a list
    without full stops) is cut at spaces.
    """
    sentences = []
    for number, text in pages:
        flowing = re.sub(r"\s*\n\s*", " ", text)
        for sentence in _SENTENCE_END.split(flowing):
            sentence = sentence.strip()
            while len(sentence) > max_chars:
                cut = sentence.rfind(" ", 0, max_chars)
                if cut <= 0:
                    cut = max_chars
                sentences.append((number, sentence[:cut]))
                sentence = sentence[cut:].strip()
            if sentence:
                sentences.append((number, sentence))
    return sentences


def make_chunks(
    pages: list[Page], size: int = CHUNK_SIZE_CHARS, overlap: int = CHUNK_OVERLAP_CHARS
) -> list[Chunk]:
    """Group sentences into chunks of up to `size` characters.

    Each chunk starts with the last sentences of the previous one (up to
    `overlap` characters), so a point that spans two chunks is still whole
    in one of them.
    """
    chunks: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    length = 0
    for page, sentence in split_sentences(pages, size):
        if current and length + len(sentence) > size:
            chunks.append(current)
            carried: list[tuple[int, str]] = []
            carried_length = 0
            for previous in reversed(current):
                if carried_length + len(previous[1]) + 1 > overlap:
                    break
                carried.insert(0, previous)
                carried_length += len(previous[1]) + 1
            current, length = carried, carried_length
        current.append((page, sentence))
        length += len(sentence) + 1
    if current:
        chunks.append(current)
    return [(group[0][0], group[-1][0], " ".join(s for _, s in group)) for group in chunks]


def chunk_records(doc: SourceDocument, pages: list[Page]) -> list[dict]:
    """The chunks of one document, with everything retrieval needs to cite them."""
    return [
        {
            "chunk_id": f"{doc.id}-{number:04d}",
            "doc_id": doc.id,
            "text": text,
            "source": doc.file,
            "title": doc.title,
            "year": doc.year,
            "page": first_page,
            "end_page": last_page,
            "language": doc.language,
            "domains": doc.domains,
            "limbs": doc.limbs,
            "source_type": doc.source_type,
        }
        for number, (first_page, last_page, text) in enumerate(make_chunks(pages))
    ]


# ---- Saving -------------------------------------------------------------


def save_store(records: list[dict], vectors: np.ndarray, info: dict, out_dir: Path) -> None:
    """Write the three store files. Each is written under a temporary name
    first, so a failed run never leaves a half-written store behind."""
    out_dir.mkdir(parents=True, exist_ok=True)
    temporary = {name: out_dir / f"{name}.tmp" for name in (VECTORS_FILE, CHUNKS_FILE, INFO_FILE)}
    with temporary[VECTORS_FILE].open("wb") as handle:  # a handle, so np.save adds no ".npy"
        np.save(handle, vectors)
    temporary[CHUNKS_FILE].write_text(
        json.dumps({"chunks": records}, ensure_ascii=False), encoding="utf-8"
    )
    temporary[INFO_FILE].write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    for name, path in temporary.items():
        os.replace(path, out_dir / name)


# ---- Whole run ----------------------------------------------------------


def ingest(
    catalog_path: Path = CATALOG_PATH,
    sources_dir: Path = SOURCES_DIR,
    extracted_dir: Path = EXTRACTED_DIR,
    out_dir: Path = VECTOR_STORE_DIR,
    embed: Optional[Callable[[list[str]], np.ndarray]] = None,
    model_name: str = EMBEDDING_MODEL_NAME,
    revision: Optional[str] = EMBEDDING_MODEL_REVISION,
) -> dict:
    """Extract, chunk, embed and save. Returns the info written to info.json."""
    extracted = extract_all(catalog_path, sources_dir, extracted_dir)
    records: list[dict] = []
    for doc, path in extracted:
        records += chunk_records(doc, read_extracted(path))
    if not records:
        print("No text to ingest. The vector store was not changed.")
        return {}

    if embed is None:
        def embed(texts: list[str]) -> np.ndarray:
            return embed_texts(texts, model_name, revision, show_progress=True)

    print(f"\nEmbedding {len(records):,} chunks with {model_name} ...")
    vectors = embed([record["text"] for record in records])

    per_document: dict[str, int] = {}
    for record in records:
        per_document[record["doc_id"]] = per_document.get(record["doc_id"], 0) + 1
    info = {
        "model": model_name,
        "revision": revision,
        "dimensions": int(vectors.shape[1]),
        "chunk_size_chars": CHUNK_SIZE_CHARS,
        "chunk_overlap_chars": CHUNK_OVERLAP_CHARS,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "chunks": len(records),
        "chunks_per_document": per_document,
    }
    save_store(records, vectors, info, out_dir)
    return info


def main() -> None:
    info = ingest()
    if info:
        print(f"Saved {info['chunks']:,} chunks ({info['dimensions']} numbers each) to {VECTOR_STORE_DIR}")


if __name__ == "__main__":
    main()
