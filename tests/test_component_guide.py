"""Tests for reasoning/component_guide.py and reasoning/fitting_guide.py: every quote is word for word on its page.

The quote checks read data/extracted/<doc_id>.txt, which `python -m
knowledge.ingest` (or `knowledge.extract`) generates and git doesn't keep;
without it they are skipped.
"""

import re
import unittest
from functools import lru_cache

from knowledge.catalog import load_catalog
from reasoning import component_guide, fitting_guide
from reasoning.component_guide import COMPONENT_KEYS, COMPONENTS, GRADES, K_LEVEL_DESCRIPTIONS
from shared.case_schema import ActivityLevel
from shared.config import EXTRACTED_DIR

_PAGE_MARKER = re.compile(r"^--- page (\d+) ---$", re.MULTILINE)

ALL_STATEMENTS = (*component_guide.ALL_STATEMENTS, *fitting_guide.ALL_STATEMENTS)
RULES = (*component_guide.RULES, *fitting_guide.RULES)


def flat(text: str) -> str:
    """Line breaks and runs of spaces as one space, as when reading the PDF."""
    return " ".join(text.split())


@lru_cache
def pages(doc_id: str) -> dict[int, str]:
    text = (EXTRACTED_DIR / f"{doc_id}.txt").read_text(encoding="utf-8")
    parts = _PAGE_MARKER.split(text)  # [header, "1", page 1, "2", page 2, ...]
    return {int(number): flat(body) for number, body in zip(parts[1::2], parts[2::2])}


def page_text(doc_id: str, quote) -> str:
    last = quote.end_page or quote.page
    return " ".join(pages(doc_id).get(n, "") for n in range(quote.page, last + 1))


def quotes_of(statement):
    return [statement.quote, *statement.context]


class GuideShapeTests(unittest.TestCase):
    def test_ids_unique_across_both_guides(self):
        # The review form and the log name a statement by its id alone.
        ids = [s.id for s in ALL_STATEMENTS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_sections_and_grades_known(self):
        for guide, keys in ((component_guide, COMPONENT_KEYS), (fitting_guide, fitting_guide.SECTION_KEYS)):
            for rule in guide.RULES:
                with self.subTest(rule.statement.id):
                    self.assertIn(rule.statement.component, keys)
                    self.assertIn(rule.statement.grade, (*GRADES, None))
                    self.assertTrue(rule.levels)
                    self.assertFalse(rule.unilateral_only and rule.bilateral_only)

    def test_documents_are_catalogued_prosthetics_sources(self):
        catalog = {doc.id: doc for doc in load_catalog()}
        for statement in ALL_STATEMENTS:
            with self.subTest(statement.id):
                self.assertIn(statement.doc_id, catalog)
                self.assertIn("prosthetics", catalog[statement.doc_id].domains)

    def test_every_k_level_described(self):
        self.assertEqual(set(K_LEVEL_DESCRIPTIONS),
                         {level.value for level in ActivityLevel if level is not ActivityLevel.UNKNOWN})

    def test_quotes_are_whole_sentences(self):
        for statement in ALL_STATEMENTS:
            for quote in quotes_of(statement):
                with self.subTest(statement.id, page=quote.page):
                    self.assertTrue(quote.text[0].isupper(), quote.text[:30])
                    if quote.items:  # a heading or "…include:", then the list
                        self.assertTrue(all(item.strip() for item in quote.items))
                    else:  # a sentence may end inside quotation marks: “stubbies.”
                        self.assertTrue(quote.text.rstrip("”’").endswith((".", "?")), quote.text[-30:])

    def test_section_order(self):
        self.assertEqual(COMPONENT_KEYS[0], "knee")
        self.assertEqual(len(COMPONENTS), len(set(COMPONENT_KEYS)))
        self.assertEqual(fitting_guide.SECTION_KEYS, ("readiness", "prosthesis_stage", "fitting", "alignment"))

    def test_readiness_fields_are_intake_fields(self):
        from shared.field_guide import FIELDS_BY_PATH
        for path in fitting_guide.READINESS_FIELDS:
            with self.subTest(path):
                self.assertIn(path, FIELDS_BY_PATH)


class QuoteTests(unittest.TestCase):
    def setUp(self):
        missing = {s.doc_id for s in ALL_STATEMENTS if not (EXTRACTED_DIR / f"{s.doc_id}.txt").is_file()}
        if missing:
            self.skipTest(f"extracted text not generated: {sorted(missing)}")

    def test_every_quote_is_on_its_page(self):
        for statement in ALL_STATEMENTS:
            for quote in quotes_of(statement):
                with self.subTest(statement.id, page=quote.page):
                    text = flat(quote.text)
                    found_on = [n for n, body in pages(statement.doc_id).items() if text in body]
                    self.assertIn(text, page_text(statement.doc_id, quote),
                                  f"not on {quote.pages}; found on pages {found_on}")

    def test_list_items_follow_their_heading_in_order(self):
        for statement in ALL_STATEMENTS:
            for quote in quotes_of(statement):
                if not quote.items:
                    continue
                with self.subTest(statement.id, page=quote.page):
                    body = page_text(statement.doc_id, quote)
                    position = body.index(flat(quote.text)) + len(flat(quote.text))
                    for item in quote.items:
                        found = body.find(flat(item), position)
                        self.assertNotEqual(found, -1, f"{item!r} not after the previous item")
                        # Only a bullet ("y", "·", "–") or nothing between items
                        self.assertLessEqual(len(body[position:found].strip()), 1, body[position:found])
                        position = found + len(flat(item))

    def test_grade_is_the_one_printed_after_the_recommendation(self):
        # VA/DoD prints e.g. "(Weak for | Reviewed, New-added)" right after it.
        for statement in ALL_STATEMENTS:
            if statement.grade is None:
                continue
            with self.subTest(statement.id):
                body = page_text(statement.doc_id, statement.quote)
                end = body.index(flat(statement.quote.text)) + len(flat(statement.quote.text))
                self.assertTrue(body[end:end + 30].startswith(f" ({statement.grade} |"),
                                body[end:end + 30])


if __name__ == "__main__":
    unittest.main()
