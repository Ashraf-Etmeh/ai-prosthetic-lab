"""Shared test helpers: a tiny stand-in for the embedding model.

The real model is 2.3 GB and slow to load, so tests use fake_embed: each
word adds 1 to one of 64 positions, then the vector is scaled to length 1.
Texts sharing words get similar vectors, which is all the tests need.
"""

import re
import zlib

import numpy as np

DIMENSIONS = 64


def fake_embed(texts: list[str]) -> np.ndarray:
    vectors = np.zeros((len(texts), DIMENSIONS), dtype=np.float32)
    for row, text in enumerate(texts):
        for word in re.findall(r"\w+", text.lower()):
            vectors[row, zlib.crc32(word.encode()) % DIMENSIONS] += 1
    lengths = np.linalg.norm(vectors, axis=1, keepdims=True)
    lengths[lengths == 0] = 1
    return vectors / lengths


def chunk_record(
    chunk_id: str, text: str, domains=("prosthetics",), language: str = "en", page: int = 1, limbs=None
) -> dict:
    """One chunk as knowledge/ingest.py stores it in chunks.json."""
    doc_id = chunk_id.rsplit("-", 1)[0]
    return {
        "chunk_id": chunk_id,
        "doc_id": doc_id,
        "text": text,
        "source": f"01_guidelines/{doc_id}.pdf",
        "title": f"Title of {doc_id}",
        "year": 2024,
        "page": page,
        "end_page": page,
        "language": language,
        "domains": list(domains),
        "limbs": None if limbs is None else list(limbs),
        "source_type": "protocol",
    }
