"""Protocol retrieval: the source passages relevant to a case's information gaps.

For every missing field of a case (shared/field_guide.py), this searches the
vector store that `python -m knowledge.ingest` builds and returns the most
similar passages, best first. Only documents whose catalog domains include
one of RETRIEVAL_DOMAINS are searched (v1: prosthetics), and none of
RETRIEVAL_EXCLUDED_DOCUMENTS.

How the search works: the query is turned into a vector with the same model
as the chunks. All vectors have length 1, so the dot product of the query
with a chunk's vector is their cosine similarity: 1 means the same meaning,
around 0 means unrelated. The chunks with the highest scores win.
"""

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from knowledge.embedding import embed_texts
from knowledge.ingest import CHUNKS_FILE, INFO_FILE, VECTORS_FILE
from knowledge.models import ProtocolChunk
from shared.case_schema import Case
from shared.config import (
    EMBEDDING_MODEL_NAME,
    EMBEDDING_MODEL_REVISION,
    RETRIEVAL_DOMAINS,
    RETRIEVAL_EXCLUDED_DOCUMENTS,
    RETRIEVAL_LANGUAGES,
    RETRIEVAL_TOP_K,
    VECTOR_STORE_DIR,
)
from shared.field_guide import build_query, missing_fields


class KnowledgeBaseMissing(RuntimeError):
    """The vector store hasn't been built yet."""


@dataclass
class VectorStore:
    vectors: np.ndarray  # one row per chunk, each of length 1
    chunks: list[dict]  # chunk i belongs to row i

    @classmethod
    def load(
        cls,
        folder: Path = VECTOR_STORE_DIR,
        model_name: str = EMBEDDING_MODEL_NAME,
        revision: Optional[str] = EMBEDDING_MODEL_REVISION,
    ) -> "VectorStore":
        info_path = folder / INFO_FILE
        if not info_path.is_file():
            raise KnowledgeBaseMissing(
                f"No vector store in {folder}. Build it with: python -m knowledge.ingest"
            )
        info = json.loads(info_path.read_text(encoding="utf-8"))
        if info["model"] != model_name or info.get("revision") != revision:
            # Vectors from two different models can't be compared.
            raise RuntimeError(
                f"The vector store was built with {info['model']} ({info.get('revision')}), "
                f"but shared/config.py names {model_name} ({revision}). "
                "Rebuild it with: python -m knowledge.ingest"
            )
        vectors = np.load(folder / VECTORS_FILE)
        chunks = json.loads((folder / CHUNKS_FILE).read_text(encoding="utf-8"))["chunks"]
        if len(chunks) != len(vectors):
            raise RuntimeError(f"{folder} is inconsistent. Rebuild it with: python -m knowledge.ingest")
        return cls(vectors, chunks)

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = RETRIEVAL_TOP_K,
        domains: Optional[Iterable[str]] = None,
        languages: Optional[Iterable[str]] = None,
        limb: Optional[str] = None,
        exclude: Iterable[str] = (),
    ) -> list[ProtocolChunk]:
        """The top_k chunks most similar to the query, best first.

        domains / languages: only chunks from documents with at least one
        of these domains, in one of these languages. None means any.
        limb: "lower" or "upper" leaves out documents only about the other
        limb. None means any.
        exclude: catalog ids of documents to leave out.
        """
        domains = None if domains is None else set(domains)
        languages = None if languages is None else set(languages)
        exclude = set(exclude)
        allowed = np.array(
            [
                (domains is None or not domains.isdisjoint(chunk["domains"]))
                and (languages is None or chunk["language"] in languages)
                and (limb is None or not chunk.get("limbs") or limb in chunk["limbs"])
                and chunk["doc_id"] not in exclude
                for chunk in self.chunks
            ],
            dtype=bool,
        )
        if not allowed.any():
            return []
        scores = np.where(allowed, self.vectors @ query_vector, -np.inf)
        best = np.argsort(-scores)[:top_k]
        return [_to_protocol_chunk(self.chunks[i], float(scores[i])) for i in best if allowed[i]]


def _to_protocol_chunk(chunk: dict, score: float) -> ProtocolChunk:
    return ProtocolChunk(
        chunk_id=chunk["chunk_id"],
        text=chunk["text"],
        source=chunk["source"],
        title=chunk["title"],
        year=chunk["year"],
        page=chunk["page"],
        end_page=chunk["end_page"],
        language=chunk["language"],
        score=round(score, 4),
    )


# One store for the whole app, reloaded if `knowledge.ingest` rebuilds it.
_cached: Optional[tuple[float, VectorStore]] = None


def get_store(folder: Path = VECTOR_STORE_DIR) -> VectorStore:
    global _cached
    info_path = folder / INFO_FILE
    if not info_path.is_file():
        raise KnowledgeBaseMissing(
            f"No vector store in {folder}. Build it with: python -m knowledge.ingest"
        )
    built_at = info_path.stat().st_mtime
    if _cached is None or _cached[0] != built_at:
        _cached = (built_at, VectorStore.load(folder))
    return _cached[1]


def search_text(
    query: str,
    top_k: int = RETRIEVAL_TOP_K,
    domains: Optional[Iterable[str]] = RETRIEVAL_DOMAINS,
    languages: Optional[Iterable[str]] = None,
    store: Optional[VectorStore] = None,
    embed: Callable[[list[str]], np.ndarray] = embed_texts,
    exclude: Iterable[str] = RETRIEVAL_EXCLUDED_DOCUMENTS,
) -> list[ProtocolChunk]:
    """Search the source library for any text (used by knowledge/evaluate.py)."""
    store = store if store is not None else get_store()
    return store.search(embed([query])[0], top_k, domains, languages, exclude=exclude)


def retrieve_relevant_chunks(
    case: Case,
    top_k: int = RETRIEVAL_TOP_K,
    store: Optional[VectorStore] = None,
    embed: Callable[[list[str]], np.ndarray] = embed_texts,
) -> dict[str, list[ProtocolChunk]]:
    """For each missing field of the case: the top_k passages, best first.

    Keys are dotted field paths, e.g. "residual_limb.volume_stability".
    Documents only about the other limb are left out: an upper-limb case
    never cites a lower-limb-only guideline.
    Raises KnowledgeBaseMissing if the vector store hasn't been built.
    """
    missing = missing_fields(case)
    if not missing:
        return {}
    store = store if store is not None else get_store()
    limb = "lower" if case.is_lower_limb else "upper"
    query_vectors = embed([build_query(case, field.info) for field in missing])
    return {
        field.info.path: store.search(
            vector, top_k, domains=RETRIEVAL_DOMAINS, languages=RETRIEVAL_LANGUAGES, limb=limb,
            exclude=RETRIEVAL_EXCLUDED_DOCUMENTS,
        )
        for field, vector in zip(missing, query_vectors)
    }
