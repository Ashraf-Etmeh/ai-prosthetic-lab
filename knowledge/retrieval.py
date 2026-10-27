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
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from knowledge.embedding import embed_texts
from knowledge.ingest import CHUNKS_FILE, INFO_FILE, VECTORS_FILE
from knowledge.models import ProtocolChunk
from shared import domains
from shared.case_schema import CaseCore
from shared.config import (
    EMBEDDING_MODEL_NAME,
    EMBEDDING_MODEL_REVISION,
    RAG_TOP_K,
    RAG_TOPIC_EXCLUDED_DOCUMENTS,
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
        per_document: Optional[int] = None,
    ) -> list[ProtocolChunk]:
        """The top_k chunks most similar to the query, best first.

        domains / languages: only chunks from documents with at least one
        of these domains, in one of these languages. None means any.
        limb: "lower" or "upper" leaves out documents only about the other
        limb. None means any.
        exclude: catalog ids of documents to leave out.
        per_document: at most this many chunks from one document (None: no
        limit). Orthotic searches use it (ORTHOTIC_PASSAGES_PER_DOCUMENT), so
        one document's table rows can't fill every place.
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
        if per_document is None:
            best = np.argsort(-scores)[:top_k]
            return [_to_protocol_chunk(self.chunks[i], float(scores[i])) for i in best if allowed[i]]
        found, taken = [], {}
        for i in np.argsort(-scores):
            if not allowed[i] or len(found) == top_k:
                break
            doc_id = self.chunks[i]["doc_id"]
            if taken.get(doc_id, 0) < per_document:
                taken[doc_id] = taken.get(doc_id, 0) + 1
                found.append(_to_protocol_chunk(self.chunks[i], float(scores[i])))
        return found


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
    case: CaseCore,
    top_k: int = RETRIEVAL_TOP_K,
    store: Optional[VectorStore] = None,
    embed: Callable[[list[str]], np.ndarray] = embed_texts,
    topics: bool = True,
) -> dict[str, list[ProtocolChunk]]:
    """The passages for the case, best first, keyed by what they were searched for.

    - For each missing field: the top_k passages. Keys are dotted field
      paths, e.g. "residual_limb.volume_stability".
    - With `topics` (the RAG, reasoning/rag_topics.py): for the functional
      level, each component and each fitting section, the RAG_TOP_K
      passages. Keys are the topic keys, e.g. "knee", "alignment"; they
      never clash with a field path. RAG_TOPIC_EXCLUDED_DOCUMENTS is left
      out here instead of RETRIEVAL_EXCLUDED_DOCUMENTS.
    Documents only about the other limb are left out: an upper-limb case
    never cites a lower-limb-only guideline. One call to the model embeds
    all the queries.
    Raises KnowledgeBaseMissing if the vector store hasn't been built.
    """
    from reasoning.rag_topics import GAPS, topics_for_case  # here: the knowledge layer doesn't need it otherwise

    missing = missing_fields(case)
    searches = [(field.info.path, build_query(case, field.info), top_k, RETRIEVAL_EXCLUDED_DOCUMENTS)
                for field in missing]
    if topics:
        searches += [(topic.key, topic.query, RAG_TOP_K, RAG_TOPIC_EXCLUDED_DOCUMENTS)
                     for topic in topics_for_case(case) if topic.part != GAPS]
    if not searches:
        return {}
    store = store if store is not None else get_store()
    limb = "lower" if case.is_lower_limb else "upper"
    searched = domains_for(case)
    per_document = domains.part(case.domain, "topics").PASSAGES_PER_DOCUMENT
    query_vectors = embed([query for _, query, _, _ in searches])
    return {
        key: store.search(vector, k, domains=searched, languages=RETRIEVAL_LANGUAGES, limb=limb, exclude=exclude,
                          per_document=per_document)
        for (key, _, k, exclude), vector in zip(searches, query_vectors)
    }


def domains_for(case) -> tuple[str, ...]:
    """The catalog domains searched for the case, as its domain says (<domain>/topics.py SEARCH_DOMAINS):
    an orthotic case searches the orthotic sources."""
    return domains.part(case.domain, "topics").SEARCH_DOMAINS


# ---- Passages for a fixed vocabulary (orthotics/sources.py, rehabilitation/sources.py) ----------------------
# A page that shows what the library says about each item of a vocabulary (a device type, a part, an
# intervention) searches each item's fixed wording, never what was typed, and keeps the passages that mention the
# item's topic words. Nothing is summarised or checked to support the case: the page quotes them as printed.

# A table of contents ("18 3.1 Moulding of EVA 18 3.2 Orthosis trim line"): never shown.
_CONTENTS_ENTRY = re.compile(r"\b\d{1,3}\s+\d{1,2}\.\d{1,2}\s")
CONTENTS_ENTRIES = 3


def topic_passages(chunks: list[ProtocolChunk], topic: str, per_item: int, per_document: int) -> list[ProtocolChunk]:
    """The first `per_item` chunks that mention the topic, at most `per_document` from one document, no table of
    contents."""
    pattern, kept, from_document = re.compile(topic, re.IGNORECASE), [], {}
    for chunk in chunks:
        if len(kept) == per_item:
            break
        if (pattern.search(chunk.text) and from_document.get(chunk.doc_id, 0) < per_document
                and len(_CONTENTS_ENTRY.findall(chunk.text)) < CONTENTS_ENTRIES):
            from_document[chunk.doc_id] = from_document.get(chunk.doc_id, 0) + 1
            kept.append(chunk)
    return kept


def search_items(
    items: dict[str, tuple[str, str]],
    cache: dict,
    searched_domains: Iterable[str],
    limb: Optional[str],
    exclude: Iterable[str] = (),
    per_item: int = 3,
    per_document: int = 2,
    candidates: int = 25,
    store: Optional[VectorStore] = None,
    embed: Callable[[list[str]], np.ndarray] = embed_texts,
) -> dict[str, list[ProtocolChunk]]:
    """key -> the passages shown for its (search text, topic words), best first ([]: none mention it).

    `cache` keeps each search by (store, limb, search text): the wording is fixed, so a page shown again needs no
    new search, and a re-ingested library is a new store. Raises KnowledgeBaseMissing if the library hasn't been
    ingested.
    """
    store = store if store is not None else get_store()
    exclude = tuple(exclude)
    todo = {key: (query, topic) for key, (query, topic) in items.items() if (id(store), limb, query) not in cache}
    if todo:
        vectors = embed([query for query, _ in todo.values()])
        for (query, topic), vector in zip(todo.values(), vectors):
            found = store.search(vector, candidates, domains=searched_domains, languages=RETRIEVAL_LANGUAGES,
                                 limb=limb, exclude=exclude)
            cache[(id(store), limb, query)] = topic_passages(found, topic, per_item, per_document)
    return {key: cache[(id(store), limb, query)] for key, (query, _) in items.items()}

