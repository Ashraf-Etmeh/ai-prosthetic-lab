"""Tests for intake/retrieval_misses.py: the offline measure of why answer-key statements miss the writer.

A tiny fake store and the fake embedder (tests/helpers.py) stand in for the
real index and model.
"""

import unittest

from intake import retrieval_misses as rm
from intake.golden_cases import read_golden_case
from knowledge.retrieval import VectorStore, retrieve_relevant_chunks
from reasoning.models import GuidelineStatement, Quote
from reasoning.rag_topics import FUNCTIONAL_LEVEL, GAPS, topics_for_case
from shared.case_schema import Case
from shared.config import GOLDEN_CASES_DIR, GOLDEN_HELD_OUT_DIR, MAX_ITEMS_PER_TOPIC, RAG_TOP_K
from tests.helpers import chunk_record, fake_embed

SOCKET_WORDS = "a total contact socket must fit the residual limb closely without pressure points"


def statement(doc_id: str = "doc_a", text: str = SOCKET_WORDS, component: str = "socket", items=()):
    return GuidelineStatement(id=f"{doc_id}_{component}", component=component, doc_id=doc_id, grade=None,
                              quote=Quote(10, text, items=tuple(items)))


def store(*records: dict) -> VectorStore:
    return VectorStore(fake_embed([r["text"] for r in records]), list(records))


def pair(rank, oracle_rank=None, case="c", topic="socket", crowded_by=None, any_rank="same") -> rm.Pair:
    any_rank = rank if any_rank == "same" else any_rank
    return rm.Pair(case=case, statement=f"s{rank}-{oracle_rank}-{any_rank}", topic=topic, doc="doc_a", rank=rank,
                   any_rank=any_rank, any_contained_rank=any_rank, oracle_rank=oracle_rank, crowded_by=crowded_by)


class GoldTests(unittest.TestCase):
    def test_gold_needs_the_same_document_and_a_shared_run_of_words(self):
        s = statement()
        same = rm.ProtocolChunk("doc_a-0001", "Intro. A total contact socket must fit the residual limb well.", "x", "t")
        other_doc = rm.ProtocolChunk("doc_b-0001", SOCKET_WORDS, "x", "t")
        too_few = rm.ProtocolChunk("doc_a-0002", "a total contact socket must be checked", "x", "t")  # 5 words in a row
        self.assertTrue(rm.is_gold(same, s))
        self.assertFalse(rm.is_gold(other_doc, s))
        self.assertFalse(rm.is_gold(too_few, s))

    def test_contained_needs_the_whole_quote(self):
        s = statement()
        whole = rm.ProtocolChunk("doc_a-0001", f"Before. {SOCKET_WORDS}. After.", "x", "t")
        part = rm.ProtocolChunk("doc_a-0002", "a total contact socket must fit the residual limb", "x", "t")
        self.assertTrue(rm.contains(whole, s))
        self.assertFalse(rm.contains(part, s))
        self.assertTrue(rm.is_gold(part, s))  # the --rag rule counts it: the ceiling is wider than "contained"

    def test_a_list_counts_as_part_of_the_statement(self):
        s = statement(text="Those who are ready for fitting:", items=["are free of pain and infection always"])
        chunk = rm.ProtocolChunk("doc_a-0001", "They are free of pain and infection always.", "x", "t")
        self.assertTrue(rm.is_gold(chunk, s))


class ReasonTests(unittest.TestCase):
    def test_reasons_in_order(self):
        self.assertIsNone(pair(RAG_TOP_K).reason)
        self.assertEqual(pair(None).reason, rm.NOT_SEARCHABLE)
        self.assertEqual(pair(12, oracle_rank=2).reason, rm.QUERY_MISMATCH)
        self.assertEqual(pair(12, oracle_rank=40).reason, rm.REPRESENTATION)
        self.assertEqual(pair(RAG_TOP_K + 1, oracle_rank=RAG_TOP_K + 1).reason, rm.REPRESENTATION)

    def test_reachable_under_another_topic_is_not_a_miss(self):
        # golden_cases --rag counts an item under any topic, so a gold passage found for another topic counts.
        p = pair(12, oracle_rank=2, any_rank=3)
        self.assertFalse(p.retrievable())
        self.assertTrue(p.reachable())
        self.assertIsNone(p.reason)

    def test_crowded_by_another_document(self):
        ranked = [rm.ProtocolChunk(f"{doc}-000{i}", "x", "x", "t") for i, doc in
                  enumerate(["doc_b", "doc_b", "doc_a", "doc_b", "doc_c", "doc_b"])]
        self.assertEqual(rm.crowding(ranked, "doc_a"), "doc_b")
        self.assertIsNone(rm.crowding(ranked[:5], "doc_a"))  # only 3 of doc_b
        self.assertIsNone(rm.crowding(ranked, "doc_b"))  # its own document doesn't crowd it out

    def test_writer_cap(self):
        cell = [pair(1, topic="alignment") for _ in range(MAX_ITEMS_PER_TOPIC + 2)] + [pair(None, topic="alignment")]
        retrievable, after_cap, beyond = rm.cap_ceiling(cell + [pair(2, topic="socket")])
        self.assertEqual(retrievable, MAX_ITEMS_PER_TOPIC + 3)
        self.assertEqual(after_cap, MAX_ITEMS_PER_TOPIC + 1)
        self.assertEqual(beyond, 3)  # seven expected in one (case, topic): three can never be covered


class MeasureTests(unittest.TestCase):
    def setUp(self):
        self.case = Case(amputation_level="transtibial", side="left")
        self.store = store(
            chunk_record("doc_a-0001", f"Socket design. {SOCKET_WORDS}."),
            chunk_record("doc_b-0001", "prosthetic socket design and socket fit for transtibial amputation"),
            chunk_record("doc_c-0001", "orthosis socket design and fit", domains=("orthotics",)),
            chunk_record("doc_d-0001", "upper limb socket design and fit", limbs=("upper",)),
        )

    def test_ranking_is_the_apps_topic_search_without_a_cut_off(self):
        found = retrieve_relevant_chunks(self.case, store=self.store, embed=fake_embed)
        for topic in topics_for_case(self.case):
            if topic.part == GAPS:
                continue
            with self.subTest(topic.key):
                ranked = rm.ranking(self.store, fake_embed([topic.query])[0], self.case)
                self.assertEqual([c.chunk_id for c in ranked[:RAG_TOP_K]], [c.chunk_id for c in found[topic.key]])
                self.assertNotIn("doc_c-0001", [c.chunk_id for c in ranked])  # orthotics: not searched
                self.assertNotIn("doc_d-0001", [c.chunk_id for c in ranked])  # the other limb only

    def test_measure_case(self):
        socket, filtered = statement(), statement(doc_id="doc_c", text="orthosis socket design and fit")
        pairs, searches = rm.measure_case("case-1", self.case, [socket, filtered], self.store, fake_embed, {})
        by_id = {p.statement: p for p in pairs}
        # The topic query ranks doc_b's general socket passage first; the statement's own words find doc_a first.
        self.assertEqual((by_id[socket.id].rank, by_id[socket.id].oracle_rank), (2, 1))
        self.assertTrue(by_id[socket.id].retrievable())
        self.assertLessEqual(by_id[socket.id].any_rank, by_id[socket.id].rank)  # the best over every topic
        self.assertIsNone(by_id[filtered.id].rank)
        self.assertIsNone(by_id[filtered.id].any_rank)
        self.assertEqual(by_id[filtered.id].reason, rm.NOT_SEARCHABLE)
        self.assertIn("socket", {s.topic for s in searches})

    def test_k_level_description_belongs_to_the_functional_level_topic(self):
        golden = read_golden_case(GOLDEN_CASES_DIR / "golden-01.json")
        statements = rm.expected_statements(golden)
        self.assertEqual(len(statements), len(golden.present) + 1)
        self.assertEqual(rm.topic_of(statements[-1]), FUNCTIONAL_LEVEL)


class ScopeAndReportTests(unittest.TestCase):
    def test_never_reads_the_held_out_cases(self):
        paths = rm.development_cases()
        self.assertTrue(paths)
        self.assertTrue(all(p.parent.resolve() == GOLDEN_CASES_DIR.resolve() for p in paths))
        held_out = {p.stem for p in GOLDEN_HELD_OUT_DIR.glob("*.json")}
        self.assertFalse(held_out & {p.stem for p in paths})

    def test_summary_and_report(self):
        pairs = [pair(1), pair(12, oracle_rank=2), pair(40, oracle_rank=40), pair(None, topic="alignment"),
                 pair(9, oracle_rank=1, any_rank=2)]
        searches = [rm.Search("c", "socket", ["doc_a", "doc_b"])]
        s = rm.summary(pairs, searches)
        self.assertEqual((s["pairs"], s["reachable"], s["own_topic"], s["other_topic_only"], s["misses"]),
                         (5, 2, 1, 1, 3))
        self.assertEqual({r: v["pairs"] for r, v in s["reasons"].items()},
                         {rm.NOT_SEARCHABLE: 1, rm.QUERY_MISMATCH: 1, rm.REPRESENTATION: 1})
        self.assertEqual(s["reasons"][rm.QUERY_MISMATCH]["near"], 1)
        self.assertEqual(s["reasons"][rm.REPRESENTATION]["far"], 1)
        self.assertEqual(s["documents"]["doc_b"]["top_k_searches"], 1)
        text = rm.report(s)
        self.assertRegex(text, r"reachable: in any topic's top 6\s+2/5 \(40%\)")
        self.assertIn("query mismatch      1", text)


if __name__ == "__main__":
    unittest.main()
