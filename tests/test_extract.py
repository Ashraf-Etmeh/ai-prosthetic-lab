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
    drop_repeated_lines,
    drop_search_syntax,
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
        self.assertEqual(drop_references(pages), ([(1, "Intro"), (2, "Discussion ends.")], 2, None))

    def test_heading_at_top_of_page_drops_the_page(self):
        pages = [(1, "Body"), (2, "REFERENCES\n1. Smith")]
        self.assertEqual(drop_references(pages), ([(1, "Body")], 2, None))

    def test_word_in_a_sentence_is_not_a_heading(self):
        pages = [(1, "See the references below for details.")]
        self.assertEqual(drop_references(pages), (pages, None, None))

    def test_heading_is_one_line_only(self):
        # "2020." ends the sentence before the heading; it is not a section number.
        pages = [(1, "Committee, 2020.\nReferences\n1. Smith")]
        self.assertEqual(drop_references(pages), ([(1, "Committee, 2020.")], 1, None))

    def test_german_numbered_heading(self):
        pages = [(1, "Nachsorge"), (2, "11. Literatur\nBjordal JM")]
        self.assertEqual(drop_references(pages), ([(1, "Nachsorge")], 2, None))

    def test_arabic_heading(self):
        pages = [(1, "المتن"), (2, "المراجع\n1. Smith")]
        self.assertEqual(drop_references(pages), ([(1, "المتن")], 2, None))

    def test_arabic_word_for_review_is_not_a_heading(self):
        pages = [(1, "المراجعة التحريرية")]  # "editorial review"
        self.assertEqual(drop_references(pages), (pages, None, None))

    def test_appendix_after_references_is_kept(self):
        pages = [(1, "Body"), (2, "11. Literatur\nSmith"), (3, "Jones"), (4, "ANHANG\nDASH-Fragebogen")]
        kept = [(1, "Body"), (4, "ANHANG\nDASH-Fragebogen")]
        self.assertEqual(drop_references(pages), (kept, 2, 4))

    def test_appendix_on_same_page_as_references(self):
        pages = [(1, "Ends.\nReferences\n1. Smith\nAnnex 1. Summary of standards\nFinancing")]
        kept = [(1, "Ends.\n\nAnnex 1. Summary of standards\nFinancing")]
        self.assertEqual(drop_references(pages), (kept, 1, 1))

    def test_scrambled_arabic_annex_heading(self):
        pages = [(1, "المتن"), (2, "المراجع\n85. Smith"), (3, ": موجز1 الملحق\nالتمويل")]
        self.assertEqual(drop_references(pages), ([(1, "المتن"), (3, ": موجز1 الملحق\nالتمويل")], 2, 3))

    def test_repeated_page_header_finds_start_of_list(self):
        pages = [
            (70, "Body ends."),
            (71, "REFERENCES\nReferences\n1. Smith"),
            (72, "PART 1\n22. Jones"),
            (73, "REFERENCES\n45. Dobson"),
        ]
        self.assertEqual(drop_references(pages), ([(70, "Body ends.")], 71, None))

    def test_contents_entry_far_away_is_not_the_start(self):
        pages = [(6, "96 المراجع\n97 الملحق"), (7, "المتن"), (108, "المراجع\n1. Smith")]
        kept = [(6, "96 المراجع\n97 الملحق"), (7, "المتن")]
        self.assertEqual(drop_references(pages), (kept, 108, None))

    def test_appendix_before_references_is_not_affected(self):
        pages = [(1, "Body\nAppendix A. Models"), (2, "References\n1. Smith")]
        self.assertEqual(drop_references(pages), ([(1, "Body\nAppendix A. Models")], 2, None))


class DropRepeatedLinesTests(unittest.TestCase):
    BODIES = ["About volume.", "About pain.", "About skin.", "About goals.", "About weight."]

    def test_headers_and_page_numbers_removed(self):
        pages = [
            (n, f"STANDARDS • PART 1\n{body}\nPage {n} of 5")
            for n, body in enumerate(self.BODIES, start=1)
        ]
        cleaned, removed = drop_repeated_lines(pages)
        self.assertEqual(removed, 2)  # the header, and "Page # of #"
        self.assertEqual(cleaned[2], (3, "About skin."))

    def test_lines_on_few_pages_kept(self):
        pages = [(n, f"Results\n{body}" if n < 3 else body) for n, body in enumerate(self.BODIES * 2, 1)]
        self.assertEqual(drop_repeated_lines(pages), (pages, 0))

    def test_short_document_untouched(self):
        pages = [(1, "Title\nA"), (2, "Title\nB")]
        self.assertEqual(drop_repeated_lines(pages), (pages, 0))


class DropSearchSyntaxTests(unittest.TestCase):
    def test_search_strategy_lines_removed(self):
        pages = [(134, "Appendix: search strategy\n"
                       "1 Amputation ('amputation'/exp OR 'amputation stump'/exp OR\n"
                       "(\"Artificial Limbs\"[Mesh] OR \"Amputees\"[Mesh] OR prosthe*[tiab])\n"
                       "Results were screened by two reviewers.")]
        cleaned, removed = drop_search_syntax(pages)
        self.assertEqual(removed, 2)
        self.assertEqual(cleaned, [(134, "Appendix: search strategy\nResults were screened by two reviewers.")])

    def test_prose_with_or_and_kept(self):
        pages = [(1, "Pain or swelling and redness, or both, and fever or chills.")]
        self.assertEqual(drop_search_syntax(pages), (pages, 0))


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
