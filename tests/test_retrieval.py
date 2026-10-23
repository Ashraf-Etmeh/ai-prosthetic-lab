"""Tests for knowledge/retrieval.py: searching the vector store."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from knowledge.retrieval import (
    KnowledgeBaseMissing,
    VectorStore,
    retrieve_relevant_chunks,
    search_text,
)
from reasoning.rag_topics import GAPS, topics_for_case
from shared.case_schema import ActivityProfile, Case, PriorDevice, ResidualLimb
from shared.field_guide import missing_fields
from tests.helpers import chunk_record, fake_embed


def make_store(*records: dict) -> VectorStore:
    return VectorStore(fake_embed([r["text"] for r in records]), list(records))


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.store = make_store(
            chunk_record("a-0000", "residual limb volume and edema before socket fitting"),
            chunk_record("b-0000", "phantom limb pain after amputation"),
            chunk_record("c-0000", "residual limb volume in orthosis users", domains=("orthotics",)),
            chunk_record("d-0000", "حجم الطرف المتبقي", language="ar"),
        )

    def search(self, query: str, **filters):
        return search_text(query, store=self.store, embed=fake_embed, **filters)

    def test_best_match_first_with_score(self):
        results = self.search("residual limb volume edema", domains=None)
        self.assertEqual(results[0].chunk_id, "a-0000")
        self.assertGreater(results[0].score, results[-1].score)

    def test_top_k(self):
        self.assertEqual(len(self.search("limb", top_k=2, domains=None)), 2)

    def test_orthotics_only_document_never_returned_in_v1(self):
        # search_text's default domains are RETRIEVAL_DOMAINS ("prosthetics",).
        results = self.search("residual limb volume in orthosis users", top_k=10)
        self.assertNotIn("c-0000", [r.chunk_id for r in results])
        self.assertIn("c-0000", [r.chunk_id for r in self.search("orthosis", top_k=10, domains=None)])

    def test_language_filter(self):
        results = self.search("limb", top_k=10, languages=["ar"])
        self.assertEqual([r.chunk_id for r in results], ["d-0000"])

    def test_nothing_allowed_gives_empty_list(self):
        self.assertEqual(self.search("limb", languages=["de"]), [])

    def test_excluded_document_never_returned(self):
        results = self.search("residual limb volume edema", top_k=10, exclude=["a"])
        self.assertNotIn("a-0000", [r.chunk_id for r in results])
        self.assertIn("b-0000", [r.chunk_id for r in results])

    def test_result_carries_citation_details(self):
        result = self.search("phantom pain", top_k=1)[0]
        self.assertEqual(result.citation, "Title of b (2024), p. 1")

    def test_per_document_limit(self):
        store = make_store(
            chunk_record("a-0000", "orthosis fitting check"),
            chunk_record("a-0001", "orthosis fitting check and skin"),
            chunk_record("a-0002", "orthosis fitting check of trim lines"),
            chunk_record("b-0000", "phantom limb pain"),
        )
        vector = fake_embed(["orthosis fitting check"])[0]
        unlimited = [r.chunk_id for r in store.search(vector, top_k=3)]
        limited = [r.chunk_id for r in store.search(vector, top_k=3, per_document=2)]
        self.assertEqual(unlimited, ["a-0000", "a-0001", "a-0002"])
        self.assertEqual(sorted(limited), ["a-0000", "a-0001", "b-0000"])


class LoadTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)

    def write_store(self, model="fake", records=1, rows=1):
        (self.folder / "info.json").write_text(json.dumps({"model": model, "revision": None}))
        chunks = [chunk_record(f"a-{i:04d}", "text") for i in range(records)]
        (self.folder / "chunks.json").write_text(json.dumps({"chunks": chunks}))
        np.save(self.folder / "vectors.npy", np.ones((rows, 4), dtype=np.float32))

    def test_missing_store(self):
        with self.assertRaises(KnowledgeBaseMissing):
            VectorStore.load(self.folder, model_name="fake", revision=None)

    def test_store_from_another_model_refused(self):
        self.write_store(model="other-model")
        with self.assertRaisesRegex(RuntimeError, "Rebuild"):
            VectorStore.load(self.folder, model_name="fake", revision=None)

    def test_vectors_and_chunks_out_of_step_refused(self):
        self.write_store(records=2, rows=3)
        with self.assertRaisesRegex(RuntimeError, "inconsistent"):
            VectorStore.load(self.folder, model_name="fake", revision=None)

    def test_valid_store_loads(self):
        self.write_store(records=2, rows=2)
        self.assertEqual(len(VectorStore.load(self.folder, model_name="fake", revision=None).chunks), 2)


class RetrieveRelevantChunksTests(unittest.TestCase):
    def setUp(self):
        self.store = make_store(
            chunk_record("a-0000", "residual limb volume and edema"),
            chunk_record("b-0000", "wound healing of the residual limb"),
        )

    def test_one_result_list_per_missing_field(self):
        case = Case(amputation_level="transtibial", side="left")
        retrieved = retrieve_relevant_chunks(case, top_k=2, store=self.store, embed=fake_embed, topics=False)
        self.assertEqual(list(retrieved), [m.info.path for m in missing_fields(case)])
        self.assertTrue(all(len(chunks) == 2 for chunks in retrieved.values()))

    def test_and_one_per_rag_topic(self):
        # The RAG's topics (reasoning/rag_topics.py) are searched in the same call, after the fields.
        case = Case(amputation_level="transtibial", side="left")
        retrieved = retrieve_relevant_chunks(case, top_k=1, store=self.store, embed=fake_embed)
        fields = [m.info.path for m in missing_fields(case)]
        topics = [t.key for t in topics_for_case(case) if t.part != GAPS]
        self.assertEqual(list(retrieved), fields + topics)
        self.assertIn("functional_level", topics)
        self.assertIn("alignment", topics)
        self.assertNotIn("knee", topics)  # no knee in a transtibial prosthesis
        self.assertTrue(all(len(retrieved[path]) == 1 for path in fields))
        self.assertTrue(all(len(retrieved[key]) == 2 for key in topics))  # RAG_TOP_K, here all 2 chunks

    def test_upper_limb_case_never_gets_lower_limb_only_documents(self):
        store = make_store(
            chunk_record("leg-0000", "wound healing of the residual limb", limbs=["lower"]),
            chunk_record("arm-0000", "wound healing after arm amputation", limbs=["upper"]),
            chunk_record("both-0000", "wound care for all amputations", limbs=["lower", "upper"]),
            chunk_record("any-0000", "wound check in the clinic"),  # not limb-specific
        )
        for level, excluded in (("transradial", "leg-0000"), ("transtibial", "arm-0000")):
            case = Case(amputation_level=level, side="left")
            retrieved = retrieve_relevant_chunks(case, top_k=10, store=store, embed=fake_embed)
            ids = {c.chunk_id for chunks in retrieved.values() for c in chunks}
            self.assertNotIn(excluded, ids, level)
            self.assertIn("both-0000", ids)
            self.assertIn("any-0000", ids)

    def test_only_retrieval_languages_searched(self):
        store = make_store(
            chunk_record("en-0000", "wound healing of the residual limb"),
            chunk_record("de-0000", "Wundheilung am Stumpf", language="de"),
        )
        case = Case(amputation_level="transtibial", side="left")
        with patch("knowledge.retrieval.RETRIEVAL_LANGUAGES", ("en", "ar")):
            retrieved = retrieve_relevant_chunks(case, top_k=10, store=store, embed=fake_embed)
        ids = {c.chunk_id for chunks in retrieved.values() for c in chunks}
        self.assertEqual(ids, {"en-0000"})

    def test_excluded_documents_not_searched(self):
        store = make_store(
            chunk_record("guideline-0000", "wound healing of the residual limb"),
            chunk_record("manual-0000", "wound healing before fitting"),
        )
        case = Case(amputation_level="transtibial", side="left")
        fields = {m.info.path for m in missing_fields(case)}
        with patch("knowledge.retrieval.RETRIEVAL_EXCLUDED_DOCUMENTS", ("manual",)):
            retrieved = retrieve_relevant_chunks(case, top_k=10, store=store, embed=fake_embed)
        ids = {c.chunk_id for key, chunks in retrieved.items() if key in fields for c in chunks}
        self.assertEqual(ids, {"guideline-0000"})
        # The RAG's topic search leaves out its own list instead (none by default).
        topic_ids = {c.chunk_id for key, chunks in retrieved.items() if key not in fields for c in chunks}
        self.assertEqual(topic_ids, {"guideline-0000", "manual-0000"})
        with patch("knowledge.retrieval.RETRIEVAL_EXCLUDED_DOCUMENTS", ("manual",)), \
                patch("knowledge.retrieval.RAG_TOPIC_EXCLUDED_DOCUMENTS", ("manual",)):
            retrieved = retrieve_relevant_chunks(case, top_k=10, store=store, embed=fake_embed)
        self.assertEqual({c.chunk_id for chunks in retrieved.values() for c in chunks}, {"guideline-0000"})

    def test_complete_case_needs_no_store(self):
        case = Case(
            amputation_level="transradial", side="right", age_years=40, body_weight_kg=70,
            etiology="trauma", months_since_amputation=6,
            residual_limb=ResidualLimb("healed", "stable", "intact", "mid-length", "none", "intact"),
            activity=ActivityProfile(description="office work", functional_goals="cycling"),
            prior_devices=[PriorDevice("body-powered hook")], comorbidities=[],
            cognitive_status="intact",
        )
        with patch("knowledge.retrieval.get_store", side_effect=AssertionError("store used")):
            self.assertEqual(retrieve_relevant_chunks(case, embed=fake_embed, topics=False), {})
        # The RAG's topics are searched for every case, complete or not.
        retrieved = retrieve_relevant_chunks(case, store=self.store, embed=fake_embed)
        self.assertEqual(set(retrieved), {t.key for t in topics_for_case(case)})
        self.assertIn("prosthesis_type", retrieved)

    def test_missing_store_raises(self):
        case = Case(amputation_level="transtibial", side="left")
        with patch("knowledge.retrieval.get_store", side_effect=KnowledgeBaseMissing("not built")):
            with self.assertRaises(KnowledgeBaseMissing):
                retrieve_relevant_chunks(case, embed=fake_embed)
