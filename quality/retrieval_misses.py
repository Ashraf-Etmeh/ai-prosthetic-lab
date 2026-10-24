"""Why expected answer-key statements don't reach the writer: the search ceiling, measured offline.

  python -m quality.retrieval_misses              the development golden cases (data/quality/golden_cases/)
  python -m quality.retrieval_misses --json FILE  also write every (case, statement) record to FILE

Needs the embedding model and the vector store (it never downloads the model)
and calls no AI and no cloud service. It never reads the held-out cases
(CLAUDE.md): measurements made to tune the search use the development cases
only. golden-13 is golden-01 entered through the Arabic form, so its pairs
repeat golden-01's, as in every golden-case count.

For each development case and each statement it expects (the component and
fitting rules, plus the K-level description), the topic the statement belongs
to is searched exactly as the app searches it (reasoning/rag_topics.py query,
knowledge/retrieval.py filters), but the whole ranking is kept:

- a gold passage is from the statement's document and shares a run of
  COVER_WORDS words with it: the rule `golden_cases --rag` uses to count a
  statement covered (covering()). That rule ignores the topic an item is
  filed under, so a statement is "reachable" at k when any component or
  fitting topic of the case has a gold passage in its top k. Every quote
  the writer can keep comes from those passages, so this is the ceiling for
  --rag coverage. Whether the whole quote sits inside one passage
  ("contained") is reported too. The 2026-10-11 figure (129/359, 36%, over
  all 13 cases, from a script that was not kept) matches "reachable" (35%
  and the same depth curve on the 8 development cases, 2026-10-16), not
  "contained" (20%).
- "own topic": a gold passage in the top k of the statement's own topic,
  where the page shows it; with the writer's cap of MAX_ITEMS_PER_TOPIC
  items per topic, at most that many per (case, topic).
- for each statement not reachable at RAG_TOP_K, why (the first that applies):
    not searchable   no passage of its document passes the app's filters with
                     the statement's words in it (document filtered out, or
                     the text is not in the index)
    query mismatch   the statement's own words as the query bring a gold
                     passage into the top k; the topic query doesn't, so its
                     wording is the problem
    representation   even the statement's own words leave every gold passage
                     below the top k: chunking, extraction or the embedding
  with the best gold passage's rank under the topic query (near: up to 30;
  far: beyond), and the document that holds CROWD or more of the top
  RAG_TOP_K passages, if one does ("crowded out").
- per document: in how many topic searches it has a passage in the top
  RAG_TOP_K and in the top 30, and how many expected pairs it holds.
- the depth curve: reachable pairs and statements, and own-topic pairs, at
  k = 6, 10, 15, 20, 30, 50.

A miss here is a measurement, not a verdict on the answer key: another passage
may say the same thing (the blueprint's "equivalent evidence"), which only a
person can judge.
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from knowledge.models import ProtocolChunk
from knowledge.retrieval import VectorStore, get_store
from prosthetics.case import Case
from prosthetics.topics import FUNCTIONAL_LEVEL
from quality.golden_cases import COVER_WORDS, K_LEVEL_BY_ID, RULES, read_golden_case, search_unavailable, shares_a_run
from reasoning.models import GuidelineStatement
from reasoning.quote_check import QuoteRefused, find_quote
from reasoning.rag_topics import GAPS, topics_for_case
from shared.config import (
    GOLDEN_CASES_DIR,
    MAX_ITEMS_PER_TOPIC,
    RAG_TOP_K,
    RAG_TOPIC_EXCLUDED_DOCUMENTS,
    RETRIEVAL_DOMAINS,
    RETRIEVAL_LANGUAGES,
)

DEPTHS = (6, 10, 15, 20, 30, 50)
NEAR = 30  # a gold passage ranked from RAG_TOP_K + 1 to here is "near"; beyond, "far"
CROWD = 4  # this many of the top RAG_TOP_K from one other document: crowded out
NOT_SEARCHABLE, QUERY_MISMATCH, REPRESENTATION = "not searchable", "query mismatch", "representation"
REASONS = (NOT_SEARCHABLE, QUERY_MISMATCH, REPRESENTATION)

Embed = Callable[[list[str]], np.ndarray]


@dataclass
class Pair:
    """One expected statement in one case, and where the search put it.

    Ranks are 1 for the first passage; None means no passage can be found at all.
    """

    case: str
    statement: str
    topic: str
    doc: str
    rank: Optional[int]  # best gold passage under its own topic's query
    any_rank: Optional[int]  # best gold passage under any component or fitting topic's query of the case
    any_contained_rank: Optional[int]  # the same, counting only passages that hold the whole quote
    oracle_rank: Optional[int]  # best gold passage with the statement's own words as the query
    crowded_by: Optional[str]  # another document holding CROWD or more of its own topic's top RAG_TOP_K, if any

    def retrievable(self, k: int = RAG_TOP_K) -> bool:
        """In its own topic's top k: shown under the right heading if the writer reports it."""
        return self.rank is not None and self.rank <= k

    def reachable(self, k: int = RAG_TOP_K) -> bool:
        """In any topic's top k: what `golden_cases --rag` can count as covered (it ignores the topic)."""
        return self.any_rank is not None and self.any_rank <= k

    @property
    def reason(self) -> Optional[str]:
        """Why it is not reachable at RAG_TOP_K, or None."""
        if self.reachable():
            return None
        if self.rank is None:
            return NOT_SEARCHABLE
        if self.oracle_rank is not None and self.oracle_rank <= RAG_TOP_K:
            return QUERY_MISMATCH
        return REPRESENTATION


@dataclass
class Search:
    """One topic search: the documents of its top passages, best first (for per-document counts)."""

    case: str
    topic: str
    top_docs: list[str]  # the documents of the top NEAR passages


def statement_text(statement: GuidelineStatement) -> str:
    """The statement as `golden_cases --rag` compares it: its quote and the list the quote introduces."""
    return " ".join([statement.quote.text, *statement.quote.items])


def topic_of(statement: GuidelineStatement) -> str:
    return FUNCTIONAL_LEVEL if statement.id in K_LEVEL_BY_ID else statement.component


def expected_statements(golden) -> list[GuidelineStatement]:
    statements = [RULES[i].statement for i in golden.present]
    level = golden.data["expected_answer"]["functional_level"]
    if level:
        statements.append(K_LEVEL_BY_ID[level])
    return statements


def ranking(store: VectorStore, vector: np.ndarray, case: Case) -> list[ProtocolChunk]:
    """Every passage the app's topic search could return for this case, best first (its filters, no cut-off)."""
    return store.search(vector, len(store.chunks), domains=RETRIEVAL_DOMAINS, languages=RETRIEVAL_LANGUAGES,
                        limb="lower" if case.is_lower_limb else "upper", exclude=RAG_TOPIC_EXCLUDED_DOCUMENTS)


def is_gold(chunk: ProtocolChunk, statement: GuidelineStatement) -> bool:
    return chunk.doc_id == statement.doc_id and shares_a_run(chunk.text, statement_text(statement))


def contains(chunk: ProtocolChunk, statement: GuidelineStatement) -> bool:
    if chunk.doc_id != statement.doc_id:
        return False
    try:
        find_quote(statement.quote.text, chunk.text)
    except QuoteRefused:
        return False
    return True


def first_rank(ranked: list[ProtocolChunk], test) -> Optional[int]:
    return next((place for place, chunk in enumerate(ranked, start=1) if test(chunk)), None)


def crowding(ranked: list[ProtocolChunk], own_doc: str) -> Optional[str]:
    counts = Counter(chunk.doc_id for chunk in ranked[:RAG_TOP_K] if chunk.doc_id != own_doc)
    doc, count = counts.most_common(1)[0] if counts else (None, 0)
    return doc if count >= CROWD else None


def measure_case(name: str, case: Case, statements: list[GuidelineStatement], store: VectorStore, embed: Embed,
                 oracle_vectors: dict[str, np.ndarray]) -> tuple[list[Pair], list[Search]]:
    """The pairs and topic searches of one case. oracle_vectors caches each statement's own embedding."""
    topics = {topic.key: topic for topic in topics_for_case(case) if topic.part != GAPS}
    new = [s for s in statements if s.id not in oracle_vectors]
    vectors = embed([topic.query for topic in topics.values()] + [statement_text(s) for s in new])
    oracle_vectors.update({s.id: vectors[len(topics) + i] for i, s in enumerate(new)})
    ranked = {key: ranking(store, vectors[i], case) for i, key in enumerate(topics)}
    searches = [Search(name, key, [chunk.doc_id for chunk in passages[:NEAR]]) for key, passages in ranked.items()]
    pairs = []
    for statement in statements:
        topic = topic_of(statement)
        passages = ranked.get(topic, [])  # a topic the case doesn't search (none expected) finds nothing
        oracle = ranking(store, oracle_vectors[statement.id], case)

        def gold(chunk, statement=statement):
            return is_gold(chunk, statement)

        def whole(chunk, statement=statement):
            return contains(chunk, statement)

        pairs.append(Pair(
            case=name, statement=statement.id, topic=topic, doc=statement.doc_id,
            rank=first_rank(passages, gold),
            any_rank=best(first_rank(other, gold) for other in ranked.values()),
            any_contained_rank=best(first_rank(other, whole) for other in ranked.values()),
            oracle_rank=first_rank(oracle, gold),
            crowded_by=crowding(passages, statement.doc_id),
        ))
    return pairs, searches


def best(ranks) -> Optional[int]:
    found = [rank for rank in ranks if rank is not None]
    return min(found) if found else None


def development_cases() -> list[Path]:
    """The development golden cases only: the held-out ones are never read here."""
    return sorted(GOLDEN_CASES_DIR.glob("*.json"))


def measure(paths: list[Path], store: VectorStore, embed: Embed) -> tuple[list[Pair], list[Search]]:
    pairs, searches, oracle_vectors = [], [], {}
    for path in paths:
        golden = read_golden_case(path)
        case_pairs, case_searches = measure_case(golden.id, golden.case, expected_statements(golden), store, embed,
                                                 oracle_vectors)
        pairs += case_pairs
        searches += case_searches
    return pairs, searches


# ---- The report -------------------------------------------------------------


def _share(part: int, whole: int) -> str:
    return f"{part}/{whole} ({100 * part / whole:.0f}%)" if whole else "0/0"


def cap_ceiling(pairs: list[Pair], k: int = RAG_TOP_K, cap: int = MAX_ITEMS_PER_TOPIC) -> tuple[int, int, int]:
    """(pairs retrievable at k, the same with at most `cap` per (case, topic), pairs beyond the cap in any case)."""
    cells: dict[tuple[str, str], list[Pair]] = defaultdict(list)
    for pair in pairs:
        cells[(pair.case, pair.topic)].append(pair)
    retrievable = sum(p.retrievable(k) for p in pairs)
    after_cap = sum(min(sum(p.retrievable(k) for p in cell), cap) for cell in cells.values())
    beyond = sum(max(len(cell) - cap, 0) for cell in cells.values())
    return retrievable, after_cap, beyond


def summary(pairs: list[Pair], searches: list[Search]) -> dict:
    statements = sorted({p.statement for p in pairs})
    depth = {k: {"reachable": sum(p.reachable(k) for p in pairs),
                 "reachable_statements": len({p.statement for p in pairs if p.reachable(k)}),
                 "own_topic": sum(p.retrievable(k) for p in pairs)} for k in DEPTHS}
    own_topic, after_cap, beyond = cap_ceiling(pairs)
    misses = [p for p in pairs if not p.reachable()]
    reasons = {reason: {"pairs": sum(p.reason == reason for p in misses),
                        "near": sum(p.reason == reason and p.rank is not None and p.rank <= NEAR for p in misses),
                        "far": sum(p.reason == reason and p.rank is not None and p.rank > NEAR for p in misses)}
               for reason in REASONS}
    topics = {topic: {"pairs": sum(p.topic == topic for p in pairs),
                      "own_topic": sum(p.topic == topic and p.retrievable() for p in pairs),
                      "reachable": sum(p.topic == topic and p.reachable() for p in pairs)}
              for topic in sorted({p.topic for p in pairs})}
    documents = {}
    for doc in sorted({d for s in searches for d in s.top_docs} | {p.doc for p in pairs}):
        documents[doc] = {
            "top_k_searches": sum(doc in s.top_docs[:RAG_TOP_K] for s in searches),
            "top_30_searches": sum(doc in s.top_docs[:NEAR] for s in searches),
            "pairs": sum(p.doc == doc for p in pairs),
            "reachable": sum(p.doc == doc and p.reachable() for p in pairs),
        }
    return {
        "settings": {"RAG_TOP_K": RAG_TOP_K, "MAX_ITEMS_PER_TOPIC": MAX_ITEMS_PER_TOPIC, "COVER_WORDS": COVER_WORDS,
                     "near": NEAR, "crowd": CROWD, "cases": len({p.case for p in pairs}), "searches": len(searches)},
        "pairs": len(pairs), "statements": len(statements),
        "reachable": sum(p.reachable() for p in pairs),
        "reachable_statements": len({p.statement for p in pairs if p.reachable()}),
        "contained": sum(p.any_contained_rank is not None and p.any_contained_rank <= RAG_TOP_K for p in pairs),
        "own_topic": own_topic, "after_cap": after_cap, "beyond_cap": beyond,
        "other_topic_only": sum(p.reachable() and not p.retrievable() for p in pairs),
        "depth": depth, "misses": len(misses), "reasons": reasons,
        "crowded": sum(p.crowded_by is not None for p in misses),
        "crowded_by": dict(Counter(p.crowded_by for p in misses if p.crowded_by).most_common()),
        "topics": topics, "documents": documents,
    }


def report(s: dict) -> str:
    n, k, cap = s["pairs"], s["settings"]["RAG_TOP_K"], s["settings"]["MAX_ITEMS_PER_TOPIC"]
    lines = [
        f"{s['settings']['cases']} development case(s), {n} (case, statement) pairs, {s['statements']} distinct "
        f"statements, {s['settings']['searches']} topic searches",
        "",
        f"At k = {k} (gold: a passage from the statement's document sharing {s['settings']['COVER_WORDS']} words in "
        "a row with it, the --rag rule):",
        f"  reachable: in any topic's top {k}       {_share(s['reachable'], n)}   "
        f"{s['reachable_statements']}/{s['statements']} statements   (the ceiling for --rag coverage)",
        f"    whole quote inside one passage    {_share(s['contained'], n)}",
        f"  in its own topic's top {k}             {_share(s['own_topic'], n)}   "
        f"({s['other_topic_only']} reachable only under another topic)",
        f"    own topic, at most {cap} per topic     {_share(s['after_cap'], n)}   "
        f"({s['beyond_cap']} pairs expect a 5th or later item in their (case, topic))",
        "",
        "Depth curve:   reachable (pairs; statements)        own topic",
        *(f"  k = {depth:>3}     {_share(v['reachable'], n):>14}   {v['reachable_statements']:2}/{s['statements']}"
          f"        {_share(v['own_topic'], n):>14}" for depth, v in s["depth"].items()),
        "",
        f"Why the {s['misses']} pairs not reachable at k = {k} are missed (rank under their own topic's query; "
        f"near: {k + 1}-{s['settings']['near']}, far: beyond):",
        *(f"  {reason:16} {v['pairs']:4}   near {v['near']:3}, far {v['far']:3}" for reason, v in s["reasons"].items()),
        f"  crowded out (one other document holds {s['settings']['crowd']}+ of the own topic's top {k}): "
        f"{s['crowded']} of them"
        + (": " + ", ".join(f"{doc} {count}" for doc, count in s["crowded_by"].items()) if s["crowded_by"] else ""),
        "",
        f"Per topic, at k = {k}:   own topic   reachable",
        *(f"  {topic:18} {_share(v['own_topic'], v['pairs']):>12}   {_share(v['reachable'], v['pairs']):>12}"
          for topic, v in s["topics"].items()),
        "",
        f"Per document: topic searches with a passage in the top {k} / top 30; expected pairs reachable at k = {k}",
        *(f"  {doc:48} {v['top_k_searches']:3} / {v['top_30_searches']:3}   "
          + (_share(v['reachable'], v['pairs']) if v["pairs"] else "-")
          for doc, v in sorted(s["documents"].items(), key=lambda item: -item[1]["top_k_searches"])),
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="python -m quality.retrieval_misses", description=__doc__.splitlines()[0])
    parser.add_argument("--json", type=Path, help="also write the summary and every pair to this file")
    args = parser.parse_args(argv)
    unavailable = search_unavailable()
    if unavailable:
        sys.exit(f"This measures the search, which is not available: {unavailable}")
    from knowledge.embedding import embed_texts  # loads the model (10-30 s) on first use

    pairs, searches = measure(development_cases(), get_store(), embed_texts)
    result = summary(pairs, searches)
    print(report(result))
    if args.json:
        args.json.write_text(json.dumps({**result, "pair_records": [asdict(p) | {"reason": p.reason} for p in pairs]},
                                        ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nWritten: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
