"""Tests for knowledge/ingest.py: sentences, chunks, and the saved vector store."""

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from knowledge.catalog import SourceDocument
from knowledge.ingest import chunk_records, ingest, make_chunks, split_sentences
from knowledge.retrieval import VectorStore
from tests.helpers import DIMENSIONS, fake_embed


class SplitSentencesTests(unittest.TestCase):
    def test_lines_joined_and_split_at_sentence_ends(self):
        pages = [(3, "The wound must be\nhealed. Volume is stable! Is pain\nrecorded?")]
        self.assertEqual(
            split_sentences(pages),
            [(3, "The wound must be healed."), (3, "Volume is stable!"), (3, "Is pain recorded?")],
        )

    def test_arabic_question_mark_ends_a_sentence(self):
        self.assertEqual(len(split_sentences([(1, "هل التأم الجرح؟ نعم.")])), 2)

    def test_long_sentence_cut_at_spaces(self):
        sentences = split_sentences([(1, "word " * 50)], max_chars=40)
        self.assertTrue(all(len(s) <= 40 for _, s in sentences))
        self.assertEqual(" ".join(s for _, s in sentences).split(), ["word"] * 50)


class MakeChunksTests(unittest.TestCase):
    def setUp(self):
        self.pages = [(n, " ".join(f"Sentence {n}.{i} is here." for i in range(10))) for n in (1, 2, 3)]

    def test_chunks_stay_near_the_size_limit(self):
        for _, _, text in make_chunks(self.pages, size=100, overlap=30):
            self.assertLessEqual(len(text), 100 + 30)

    def test_next_chunk_repeats_the_end_of_the_previous_one(self):
        chunks = make_chunks(self.pages, size=100, overlap=30)
        last_sentence = chunks[0][2].rsplit(". ", 1)[-1]
        self.assertTrue(chunks[1][2].startswith(last_sentence))

    def test_pages_are_tracked(self):
        chunks = make_chunks(self.pages, size=100, overlap=30)
        self.assertEqual(chunks[0][0], 1)
        self.assertEqual(chunks[-1][1], 3)
        self.assertTrue(any(first != last for first, last, _ in chunks))  # one crosses a page break

    def test_all_text_kept(self):
        joined = " ".join(text for _, _, text in make_chunks(self.pages, size=100, overlap=0))
        for n in (1, 2, 3):
            self.assertIn(f"Sentence {n}.9 is here.", joined)

    def test_no_pages_no_chunks(self):
        self.assertEqual(make_chunks([]), [])


class ChunkRecordTests(unittest.TestCase):
    def test_ids_and_citation_details(self):
        doc = SourceDocument(
            id="test_doc_2024", file="01_guidelines/test.pdf", title="Test guideline",
            authors="T", year=2024, publisher="P", source_type="protocol",
            domains=["prosthetics"], language="de",
        )
        [record] = chunk_records(doc, [(7, "Ein kurzer Satz.")])
        self.assertEqual(record["chunk_id"], "test_doc_2024-0000")
        self.assertEqual((record["page"], record["language"], record["year"]), (7, "de", 2024))
        self.assertEqual(record["domains"], ["prosthetics"])


class IngestTests(unittest.TestCase):
    def test_store_written_and_loadable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sources = root / "sources"
            (sources / "01_guidelines").mkdir(parents=True)
            (sources / "01_guidelines" / "doc.txt").write_text(
                "Residual limb volume must be stable before casting. " * 30, encoding="utf-8"
            )
            catalog = sources / "catalog.json"
            catalog.write_text(json.dumps({"documents": [{
                "id": "doc_2024", "file": "01_guidelines/doc.txt", "title": "Doc",
                "authors": "A", "year": 2024, "publisher": "P", "source_type": "protocol",
                "domains": ["prosthetics"], "language": "en",
            }]}), encoding="utf-8")

            with redirect_stdout(StringIO()):
                info = ingest(catalog, sources, root / "extracted", root / "store",
                              embed=fake_embed, model_name="fake", revision=None)

            store = VectorStore.load(root / "store", model_name="fake", revision=None)
            self.assertEqual(info["chunks"], len(store.chunks))
            self.assertEqual(store.vectors.shape, (len(store.chunks), DIMENSIONS))
            self.assertEqual(store.chunks[0]["chunk_id"], "doc_2024-0000")
            self.assertEqual(sorted(p.name for p in (root / "store").iterdir()),
                             ["chunks.json", "info.json", "vectors.npy"])

    def test_no_documents_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with redirect_stdout(StringIO()):
                info = ingest(root / "catalog.json", root, root / "extracted", root / "store",
                              embed=fake_embed, model_name="fake", revision=None)
            self.assertEqual(info, {})
            self.assertFalse((root / "store").exists())
