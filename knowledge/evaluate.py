"""Retrieval evaluation: does the search find the page that answers a question?

Run:  python -m knowledge.evaluate      (after python -m knowledge.ingest)
      --orthotics: the orthotic topic searches instead; --record: add the result to
      data/quality/results/runs.jsonl (quality/results.py) for the source and quality pages

Reads data/knowledge/eval/retrieval_queries.json. Each query names the document and
pages that answer it. The script searches the documents v1 searches
(RETRIEVAL_DOMAINS, without RETRIEVAL_EXCLUDED_DOCUMENTS) and reports, per
group of queries:
- hit@1: how often the first result is from the right pages,
- hit@5: how often one of the top 5 is.
It runs twice: with all documents, then without the German ones, so you can
see whether adding German changes the English and Arabic results.
Finally it compares the similarity scores of correct answers with those of
the off-topic queries, which is what MIN_RELEVANCE_SCORE is chosen from.
"""

import json
import statistics
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from knowledge.catalog import LANGUAGES
from knowledge.embedding import embed_texts
from knowledge.models import ProtocolChunk
from knowledge.retrieval import VectorStore, get_store
from shared.config import (
    EVAL_QUERIES_PATH,
    MIN_RELEVANCE_SCORE,
    ORTHOTIC_TOPICS_PATH,
    RETRIEVAL_DOMAINS,
    RETRIEVAL_EXCLUDED_DOCUMENTS,
    RETRIEVAL_LANGUAGES,
)

TOP_K = 5
OFF_TOPIC = "Off-topic"


@dataclass
class QueryResult:
    query: dict
    results: list[ProtocolChunk]
    rank: Optional[int]  # position of the first correct result (1 = first); None if not in the top TOP_K

    @property
    def hit_score(self) -> Optional[float]:
        return None if self.rank is None else self.results[self.rank - 1].score


def is_answer(chunk: ProtocolChunk, expected: list[dict]) -> bool:
    """True if the chunk comes from one of the expected documents and pages."""
    return any(
        chunk.doc_id == place["doc"]
        and chunk.page <= place["pages"][1]
        and (chunk.end_page or chunk.page) >= place["pages"][0]
        for place in expected
    )


def run(
    queries: list[dict],
    store: VectorStore,
    embed: Callable[[list[str]], np.ndarray],
    leave_out_languages: frozenset[str] = frozenset(),
) -> list[QueryResult]:
    vectors = embed([q["query"] for q in queries])
    outcomes = []
    for query, vector in zip(queries, vectors):
        languages = set(query.get("search_languages") or LANGUAGES) - leave_out_languages
        results = store.search(vector, TOP_K, domains=RETRIEVAL_DOMAINS, languages=languages,
                               exclude=RETRIEVAL_EXCLUDED_DOCUMENTS)
        rank = next((i for i, c in enumerate(results, 1) if is_answer(c, query["expected"])), None)
        outcomes.append(QueryResult(query, results, rank))
    return outcomes


def hit_table(outcomes: list[QueryResult]) -> dict[str, tuple[int, int, int]]:
    """group -> (queries, hit@1, hit@5), off-topic queries left out."""
    table: dict[str, tuple[int, int, int]] = {}
    for outcome in outcomes:
        group = outcome.query["group"]
        if group == OFF_TOPIC:
            continue
        n, at1, at5 = table.get(group, (0, 0, 0))
        table[group] = (n + 1, at1 + (outcome.rank == 1), at5 + (outcome.rank is not None))
    return table


def report(with_german: list[QueryResult], without_german: list[QueryResult]) -> None:
    print(f"{'group':16} {'queries':>7} {'hit@1':>7} {'hit@5':>7}   hit@5 without German documents")
    other = hit_table(without_german)
    for group, (n, at1, at5) in hit_table(with_german).items():
        without = f"{other[group][2]}/{other[group][0]}" if group in other else "-"
        print(f"{group:16} {n:>7} {at1:>4}/{n:<2} {at5:>4}/{n:<2}   {without}")
    print(f"(The app's gap search uses only: {', '.join(RETRIEVAL_LANGUAGES)}; "
          "shared/config.py RETRIEVAL_LANGUAGES.)")
    if RETRIEVAL_EXCLUDED_DOCUMENTS:
        print(f"(Not searched: {', '.join(RETRIEVAL_EXCLUDED_DOCUMENTS)}; "
              "shared/config.py RETRIEVAL_EXCLUDED_DOCUMENTS.)")

    print("\nQueries whose answer was not in the top 5:")
    for outcome in with_german:
        if outcome.query["group"] != OFF_TOPIC and outcome.rank is None:
            top = outcome.results[0] if outcome.results else None
            found = f"{top.citation[:60]} ({top.score:.2f})" if top else "nothing"
            print(f"  {outcome.query['id']}: {outcome.query['query'][:60]}  -> first result: {found}")

    hits = [o.hit_score for o in with_german if o.hit_score is not None]
    off_topic = [o.results[0].score for o in with_german if o.query["group"] == OFF_TOPIC and o.results]
    print("\nSimilarity scores")
    if hits:
        print(f"  correct answers:      lowest {min(hits):.2f}, median {statistics.median(hits):.2f}")
    if off_topic:
        print(f"  off-topic best match: highest {max(off_topic):.2f}")
    print(f"  MIN_RELEVANCE_SCORE now {MIN_RELEVANCE_SCORE}: it should sit above the off-topic "
          "scores and below most correct answers.")


def load_queries(path: Path = EVAL_QUERIES_PATH) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["queries"]


# ---- Orthotics (added 2026-10-22): the app's own topic searches -------------


def orthotic_topic_ranks(
    path: Path = ORTHOTIC_TOPICS_PATH,
    store: Optional[VectorStore] = None,
    embed: Callable[[list[str]], np.ndarray] = embed_texts,
) -> list[tuple[str, str, Optional[int], list[ProtocolChunk]]]:
    """(case id, topic, rank of the first right passage or None, passages) for every case and listed topic.

    Runs knowledge/retrieval.py retrieve_relevant_chunks: the very searches the
    app makes for the case (orthotics/topics.py), so it
    measures what the AI would be given. A topic the case doesn't search (a
    field it recorded) is skipped.
    """
    from knowledge.retrieval import retrieve_relevant_chunks  # here: the prosthetic run doesn't need it
    from shared.case_schema import case_from_dict

    data = json.loads(path.read_text(encoding="utf-8"))
    store = store if store is not None else get_store()
    rows = []
    for entry in data["cases"]:
        found = retrieve_relevant_chunks(case_from_dict(entry["case"]), store=store, embed=embed)
        for topic, expected in data["topics"].items():
            if topic not in found:
                continue
            chunks = found[topic]
            rank = next((i for i, c in enumerate(chunks, 1) if is_answer(c, expected)), None)
            rows.append((entry["id"], topic, rank, chunks))
    return rows


def orthotic_report(rows) -> None:
    from collections import Counter

    cases = list(dict.fromkeys(case for case, _, _, _ in rows))
    topics = list(dict.fromkeys(topic for _, topic, _, _ in rows))
    rank = {(case, topic): r for case, topic, r, _ in rows}
    print(f"{'topic':32} " + " ".join(f"{case:>12}" for case in cases))
    for topic in topics:
        cells = [rank.get((case, topic), "-") for case in cases]
        print(f"{topic:32} " + " ".join(f"{('-' if c == '-' else (c if c else 'miss')):>12}" for c in cells))
    hits = sum(1 for _, _, r, _ in rows if r)
    print(f"\nTopic searches with a right passage among those the AI sees: {hits}/{len(rows)}")
    documents = Counter(chunk.doc_id for _, _, _, chunks in rows for chunk in chunks)
    print("Passages per document across these searches:",
          ", ".join(f"{doc} {n}" for doc, n in documents.most_common()))


def _record(data: dict) -> None:
    """Add the result to data/quality/results/runs.jsonl (quality/results.py), for the source and quality pages."""
    from quality import results  # here: only a recorded run needs it

    results.record_run(results.SEARCH_QUALITY, data)
    print(f"Recorded in {results.config.QUALITY_RESULTS_PATH}")


def main(
    store: Optional[VectorStore] = None,
    embed: Callable[[list[str]], np.ndarray] = embed_texts,
    orthotics: bool = False,
    record: bool = False,
) -> None:
    if orthotics:
        rows = orthotic_topic_ranks(store=store, embed=embed)
        orthotic_report(rows)
        if record:
            _record({"orthotics": True, "searches": len(rows), "hits": sum(1 for _, _, r, _ in rows if r)})
        return
    queries = load_queries()
    store = store if store is not None else get_store()
    # Queries that need the German documents can't run without them.
    not_german = [
        q for q in queries if q["group"] != "German" and q.get("search_languages") != ["de"]
    ]
    outcomes = run(queries, store, embed)
    report(outcomes, run(not_german, store, embed, frozenset({"de"})))
    if record:
        table = hit_table(outcomes)
        _record({"orthotics": False, "queries": sum(n for n, _, _ in table.values()),
                 "hit_at_1": sum(at1 for _, at1, _ in table.values()),
                 "hit_at_5": sum(at5 for _, _, at5 in table.values()),
                 "groups": {group: {"queries": n, "hit_at_1": at1, "hit_at_5": at5}
                            for group, (n, at1, at5) in table.items()}})


if __name__ == "__main__":
    import sys

    main(orthotics="--orthotics" in sys.argv[1:], record="--record" in sys.argv[1:])


