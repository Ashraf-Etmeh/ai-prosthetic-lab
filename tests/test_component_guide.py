"""Tests for reasoning/component_guide.py: every quote is word for word on its page.

The quote checks read data/extracted/<doc_id>.txt, which `python -m
knowledge.ingest` (or `knowledge.extract`) generates and git doesn't keep;
without it they are skipped.
"""

import re
import unittest
from functools import lru_cache

from knowledge.catalog import load_catalog
from reasoning.component_guide import (
    ALL_STATEMENTS,
    COMPONENT_KEYS,
    COMPONENTS,
    GRADES,
    K_LEVEL_DESCRIPTIONS,
    RULES,
)
from shared.case_schema import ActivityLevel
from shared.config import EXTRACTED_DIR

_PAGE_MARKER = re.compile(r"^--- page (\d+) ---$", re.MULTILINE)


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
    def test_ids_unique(self):
        ids = [s.id for s in ALL_STATEMENTS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_components_and_grades_known(self):
        for rule in RULES:
            with self.subTest(rule.statement.id):
                self.assertIn(rule.statement.component, COMPONENT_KEYS)
                self.assertIn(rule.statement.grade, (*GRADES, None))
                self.assertTrue(rule.levels)

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
                    self.assertTrue(quote.text.endswith("."), quote.text[-30:])

    def test_component_order_lower_limb_first(self):
        self.assertEqual(COMPONENT_KEYS[0], "knee")
        self.assertEqual(len(COMPONENTS), len(set(COMPONENT_KEYS)))


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
