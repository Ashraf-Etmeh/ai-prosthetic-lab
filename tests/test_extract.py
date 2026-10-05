"""Tests for knowledge/extract.py: cleaning, removing references, extracted-text files.

The real PDFs are not in git, so these tests use short strings and .txt files.
"""

import tempfile
import unittest
from pathlib import Path

from knowledge.catalog import SourceDocument
from knowledge.extract import (
    check_arabic,
    clean_text,
    drop_references,
    extract_document,
    read_extracted,
    write_extracted,
)


def make_doc(**changes) -> SourceDocument:
    fields = {
        "id": "test_doc",
        "file": "test_doc.txt",
        "title": "Test",
        "authors": "Tester T",
        "year": 2024,
        "publisher": "Nobody",
        "source_type": "protocol",
        "domains": ["prosthetics"],
        "language": "en",
    }
    fields.update(changes)
    return SourceDocument(**fields)


class CleanTextTests(unittest.TestCase):
    def test_ligatures_become_plain_letters(self):
        self.assertEqual(clean_text("ﬁtting and ﬂexion"), "fitting and flexion")

    def test_arabic_display_shapes_become_normal_letters(self):
        # U+FEFB is the joined display shape of lam + alef.
        self.assertEqual(clean_text("ﻻ"), "لا")

    def test_words_split_across_lines_are_joined(self):
        self.assertEqual(clean_text("orthopaedic treat-\nment"), "orthopaedic treatment")

    def test_real_compound_keeps_its_hyphen(self):
        text = "An ankle-foot orthosis. The ankle-\nfoot complex."
        self.assertEqual(clean_text(text), "An ankle-foot orthosis. The ankle-foot complex.")

    def test_table_of_contents_dots_removed(self):
        self.assertEqual(clean_text("Introduction ............ 1"), "Introduction 1")

    def test_spacing_tidied(self):
        self.assertEqual(clean_text("  a   b \n\n\n\n c  "), "a b\n\nc")


class DropReferencesTests(unittest.TestCase):
    def test_cut_at_heading_keeps_text_before_it(self):
        pages = [(1, "Intro"), (2, "Discussion ends.\nReferences\n1. Smith"), (3, "2. Jones")]
        self.assertEqual(drop_references(pages), ([(1, "Intro"), (2, "Discussion ends.")], 2))

    def test_heading_at_top_of_page_drops_the_page(self):
        pages = [(1, "Body"), (2, "REFERENCES\n1. Smith")]
        self.assertEqual(drop_references(pages), ([(1, "Body")], 2))

    def test_word_in_a_sentence_is_not_a_heading(self):
        pages = [(1, "See the references below for details.")]
        self.assertEqual(drop_references(pages), (pages, None))


class ArabicCheckTests(unittest.TestCase):
    def test_normal_arabic_passes(self):
        self.assertEqual(check_arabic("بتر الطرف السفلي " * 20), [])

    def test_display_shapes_warned(self):
        [warning] = check_arabic("ﻻﺎ" * 100)
        self.assertIn("display shapes", warning)

    def test_no_arabic_warned(self):
        [warning] = check_arabic("only English text here")
        self.assertIn("almost no Arabic", warning)


class ExtractedFileTests(unittest.TestCase):
    def test_txt_source_written_and_read_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            body = "Residual limb volume should be stable before casting. " * 3
            (folder / "test_doc.txt").write_text(body + "\nReferences\n1. Smith", encoding="utf-8")

            extracted = extract_document(make_doc(), sources_dir=folder)
            path = write_extracted(extracted, out_dir=folder / "extracted")

            self.assertEqual(extracted.warnings, [])
            self.assertEqual(extracted.references_from_page, 1)
            self.assertEqual(path.name, "test_doc.txt")
            self.assertNotIn("Smith", path.read_text(encoding="utf-8"))
            self.assertEqual(read_extracted(path), extracted.pages)
