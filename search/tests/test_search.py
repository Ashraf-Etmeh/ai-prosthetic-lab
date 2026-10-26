"""Tests for smart search (use case 05; plan Part 6, 2026-10-25): search/engine.py (filters, the local search, the AI
part behind the owner's switch), search/log.py (searches, marks, suggestions, never who asked) and the page."""

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from knowledge.catalog import load_catalog
from knowledge.tests.test_retrieval import make_store
from prosthetics.tests.helpers import catalogued_passage
from search import engine
from search import log as search_log
from shared import config
from shared.testing import FakeWriter, RouteTestCase, chunk_record, fake_embed, visible_text

SOCKS = catalogued_passage("lower_limb_amputation_va_dod_cpg_2024-0901",
                           "Socks can be added to a pin-lock socket as the residual limb volume falls during the day.", 40)
ARABIC = replace(catalogued_passage("who_po_standards_part1_arabic_2019-0901",
                                    "يُقاس حجم الطرف المتبقي قبل صنع التجويف النهائي.", 12), language="ar")


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog()
        self.recent = next(d for d in self.catalog if d.source_type == "protocol" and d.year >= 2020)
        self.older = next(d for d in self.catalog if d.source_type == "protocol" and d.year < 2020)
        self.manual = next(d for d in self.catalog if d.source_type == "professional_knowledge")
        self.store = make_store(
            chunk_record(f"{self.recent.id}-0001", "socket volume change socks", domains=("prosthetics",)),
            chunk_record(f"{self.older.id}-0001", "socket volume change consensus", domains=("prosthetics",)),
            chunk_record(f"{self.manual.id}-0001", "socket volume change manual", domains=("orthotics",)),
            chunk_record("ar_x-0001", "حجم التجويف", language="ar"))

    def find(self, **filters):
        return {c.chunk_id for c in engine.find("socket volume change", engine.Filters(**filters), store=self.store,
                                                embed=fake_embed, catalog=self.catalog)}

    def test_filters_narrow_the_search(self):
        everything = {f"{self.recent.id}-0001", f"{self.older.id}-0001", f"{self.manual.id}-0001", "ar_x-0001"}
        self.assertEqual(self.find(), everything)  # every domain, kind and language the app searches
        self.assertNotIn(f"{self.manual.id}-0001", self.find(domains=("prosthetics",)))
        self.assertNotIn(f"{self.manual.id}-0001", self.find(kinds=("protocol",)))
        self.assertEqual(self.find(kinds=("professional_knowledge",)), {f"{self.manual.id}-0001", "ar_x-0001"})
        self.assertNotIn(f"{self.older.id}-0001", self.find(from_year=2020))
        self.assertEqual(self.find(language="ar"), {"ar_x-0001"})

    def test_the_ai_answers_over_checked_quotes(self):
        answer = engine.summarise("socks and volume", [SOCKS], FakeWriter())
        self.assertEqual(answer.part.status, "ok")
        [statement] = answer.statements
        self.assertIn("Socks can be added", statement.statement.quote.text)
        self.assertEqual(statement.summary("en"), "AI sentence about question.")

    def test_a_typed_question_never_reaches_a_cloud_writer_while_switched_off(self):
        writer = FakeWriter()
        with patch.object(engine, "is_cloud", return_value=True):
            answer = engine.summarise("socks and volume", [SOCKS], writer)
            self.assertEqual((answer.part.status, answer.part.reason), ("unavailable", engine.AI_OFF_REASON))
            self.assertEqual(writer.calls, [])
            with patch.object(config, "SEARCH_CLOUD_AI", True):  # the owner switches it on
                self.assertEqual(engine.summarise("socks", [SOCKS], writer).part.status, "ok")
        system, user, schema = writer.calls[0]
        self.assertIn('"question": "socks"', user)
        self.assertIn("never advise", system.lower())

    def test_no_passage_no_call(self):
        writer = FakeWriter()
        answer = engine.summarise("anything", [], writer)
        self.assertEqual((answer.part.status, answer.statements, writer.calls), ("no passages", [], []))


class SearchLogTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "search_log.jsonl"

    def test_searches_marks_and_suggestions_counted_never_who(self):
        entry = search_log.log_search("q", {"domains": []}, ["c1"], {"kept": 2}, {}, "en", self.path)
        search_log.log_search("q2", {}, [], {"kept": 0}, {}, "ar", self.path)
        search_log.log_mark(entry["id"], "summary_wrong", self.path)
        search_log.log_suggestion(entry["id"], "q", "  a review on liners  ", self.path)
        entries = search_log.read_log(self.path)
        self.assertEqual(search_log.counts(entries), {"searches": 2, "answered": 1, "no_passage": 1, "suggestions": 1,
                                                       "marks": {"useful": 0, "not_useful": 0, "summary_wrong": 1}})
        self.assertEqual(entries[-1]["note"], "a review on liners")
        for line in entries:
            self.assertFalse({"who", "user", "ip"} & set(line))
        for search_id, mark in (("not-an-id", "useful"), (entry["id"], "best")):
            with self.subTest(mark=mark), self.assertRaises(ValueError):
                search_log.log_mark(search_id, mark, self.path)


class SearchPageTests(RouteTestCase):
    def setUp(self):
        super().setUp()
        self.log_file = self.cases_dir.parent / "search_log.jsonl"
        for replaced in (patch.object(config, "SEARCH_LOG_PATH", self.log_file),
                         patch("search.routes.find", side_effect=self.fake_find)):
            replaced.start()
            self.addCleanup(replaced.stop)
        self.found = [SOCKS, ARABIC]

    def fake_find(self, question, filters):
        self.filters = filters
        return list(self.found)

    def get(self, url, lang="en"):
        self.client.set_cookie("lang", lang)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        return resp.get_data(as_text=True)

    def test_the_page_before_a_question(self):
        html = self.get("/search")
        self.assertIn('<span class="ui-part">/ Search and education</span>', html)
        self.assertIn('<a href="/search" aria-current="page">1 Smart search</a>', html)
        self.assertIn("Type a question to search the library.", visible_text(html))
        self.assertEqual(search_log.read_log(self.log_file), [])  # nothing searched, nothing logged

    def test_a_search_lists_passages_in_their_language_and_what_the_sources_say(self):
        text = visible_text(self.get("/search?q=socks+and+volume&domain=prosthetics&kind=protocol&language=both&year=2020"))
        self.assertEqual((self.filters.domains, self.filters.kinds, self.filters.from_year),
                         (("prosthetics",), ("protocol",), 2020))
        for shown in ("What the sources say", "AI summary · 1 sentences, each quote checked", "Socks can be added",
                      "Nothing here is ranked or recommended", "Passages found",
                      "يُقاس حجم الطرف المتبقي", "quoted in Arabic, never translated", "Search runs on this machine"):
            self.assertIn(shown, text)
        [entry] = search_log.read_log(self.log_file)
        self.assertEqual((entry["question"], entry["passages"], entry["summary"]["kept"]),
                         ("socks and volume", [SOCKS.chunk_id, ARABIC.chunk_id], 1))
        self.assertNotIn("who", entry)
        self.assertIn("البحث الذكي في المكتبة المتخصصة", visible_text(self.get("/search?q=socks", "ar")))

    def test_with_the_owners_switch_off_no_summary_and_the_passages_still_shown(self):
        with patch("search.engine.is_cloud", return_value=True):
            text = visible_text(self.get("/search?q=socks"))
        self.assertIn("No AI summary: a question is typed text", text)
        self.assertIn("Socks can be added", text)  # the passage
        self.assertIn("Nothing: the AI summary is switched off, so the question stays here", text)
        self.assertNotIn("The library gave no answer", text)

    def test_a_mark_is_logged_and_the_search_not_logged_twice(self):
        self.get("/search?q=socks")
        search_id = search_log.read_log(self.log_file)[0]["id"]
        resp = self.client.post("/search/mark", data={"search_id": search_id, "mark": "useful", "q": "socks",
                                                      "language": "both"})
        self.assertEqual(resp.status_code, 302)
        self.assertIn(f"logged={search_id}", resp.headers["Location"])
        self.assertIn("Your mark is kept in the search log.", visible_text(self.get(resp.headers["Location"])))
        self.assertEqual([e["kind"] for e in search_log.read_log(self.log_file)], ["search", "mark"])
        self.assertEqual(self.client.post("/search/mark", data={"search_id": search_id, "mark": "best"}).status_code, 400)

    def test_no_passage_says_so_and_offers_a_suggestion(self):
        self.found = []
        text = visible_text(self.get("/search?q=gait+laboratory+norms"))
        self.assertIn("The library gave no answer to this question.", text)
        self.assertIn("Nothing has been written in its place.", text)
        search_id = search_log.read_log(self.log_file)[0]["id"]
        resp = self.client.post("/search/suggest", data={"search_id": search_id, "q": "gait laboratory norms",
                                                         "note": "a gait lab handbook"})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(search_log.read_log(self.log_file)[-1]["note"], "a gait lab handbook")
        self.assertIn("1 sources suggested from searches", visible_text(self.get("/knowledge")))
        self.assertIn("Smart search: 1 searches", visible_text(self.get("/quality")))


if __name__ == "__main__":
    unittest.main()
