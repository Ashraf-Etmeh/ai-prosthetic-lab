"""Tests for the reasoning and review part's own pages (plan Part 4, 2026-10-25; SYSTEM_DESIGN.md §7.2): the pathway
and its guards, quality and audit with the release gate, the link to the latest case's review, and the header's
entry for the shared part."""

from unittest.mock import patch

from prosthetics.tests.helpers import ProstheticRouteTestCase
from quality import results
from shared.store import store
from shared.testing import visible_text


class PathwayAndQualityTests(ProstheticRouteTestCase):
    def setUp(self):
        super().setUp()
        # The quality page's records: temporary, never the real data/quality/ files.
        self.results_path = self.cases_dir.parent / "runs.jsonl"
        self.releases_path = self.cases_dir.parent / "releases.csv"
        for target, value in (("QUALITY_RESULTS_PATH", self.results_path), ("RELEASES_PATH", self.releases_path)):
            replaced = patch.object(results.config, target, value)
            replaced.start()
            self.addCleanup(replaced.stop)

    def text(self, url, lang="en"):
        self.client.set_cookie("lang", lang)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200, url)
        return visible_text(resp.get_data(as_text=True))

    def test_the_pathway_names_the_guards_and_what_is_built(self):
        text = self.text("/reasoning")
        for shown in ("The reasoning pathway and its guardrails", "Guard: local search only",
                      "Guard: every quote checked word for word", "A ranking of components or options",
                      "Built: a sentence whose quote fails is removed", "Measured only:", "Not built:",
                      "draft", "Prosthetics sends the amputation level, side and recorded K-level"):
            self.assertIn(shown, text)
        # Each domain's cloud switch as the settings have it: orthotics off by the owner's decision.
        self.assertIn("not sent: switched off by the owner", text)
        self.assertIn("مسار الاستدلال وضوابطه", self.text("/reasoning", "ar"))

    def test_quality_before_anything_is_recorded(self):
        text = self.text("/quality")
        for shown in ("Quality and audit", "Not recorded yet: python scripts/verify_all.py --record",
                      "Not run yet: only when the owner asks, never tuned on", "Awaiting the owner",
                      "texts awaiting an Arabic-reading specialist's check"):
            self.assertIn(shown, text)
        self.assertIn("الجودة والتدقيق", self.text("/quality", "ar"))

    def test_quality_shows_what_was_recorded_and_signed(self):
        results.record_run(results.RELEASE_CHECK, {"steps": {"unit tests": "OK"}, "unit_tests": {"ok": True, "ran": 600}})
        results.record_run(results.GOLDEN_CASES, {"set": results.DEVELOPMENT, "mode": results.NO_SEARCH,
                                                  "cases": 11, "passed": 11, "failed_cases": []})
        results.record_run(results.GOLDEN_CASES, {"set": results.DEVELOPMENT, "mode": results.RAG, "cases": 8,
                                                  "passed": 8, "rag": {"expected": 34, "covered": 6}})
        self.releases_path.write_text("release,signed_off_by,signed_on,arabic_checked_by,arabic_checked_on,note\n"
                                      "rc1,The owner,2026-10-26,An Arabic reader,2026-10-26,\n", encoding="utf-8")
        self.post_intake(amputation_level="transfemoral", k_level="K3")
        text = self.text("/quality")
        for shown in ("8 / 8", "18%", "6 of 34", "600 passed", "Checked by An Arabic reader on 2026-10-26",
                      "Release rc1 signed off by The owner on 2026-10-26", "Development cases: 8 of 8 passed",
                      "not recorded (no login yet)"):
            self.assertIn(shown, text)

    def test_the_review_tab_opens_the_latest_case(self):
        emptied = patch.object(store, "_records", {})  # other tests' cases stay in memory otherwise
        emptied.start()
        self.addCleanup(emptied.stop)
        resp = self.client.get("/review")
        self.assertTrue(resp.headers["Location"].endswith("/intake"))  # no case yet: the intake
        case_id = self.post_intake().headers["Location"].rsplit("/", 1)[-1]
        self.assertTrue(self.client.get("/review").headers["Location"].endswith(f"/review/{case_id}"))

    def test_the_header_lists_the_shared_part_next_to_the_domains(self):
        html = self.client.get("/quality").get_data(as_text=True)
        self.assertIn('<span class="ui-part">/ Reasoning and review</span>', html)
        self.assertIn('<a href="/reasoning" aria-current="true">Reasoning and review</a>', html)
        self.assertIn('<a href="/quality" aria-current="page">3 Quality and audit</a>', html)
        self.assertNotIn('class="ui-casebar"', html)  # no case on a shared part's page
        prosthetic = self.client.get("/prosthetics").get_data(as_text=True)
        self.assertIn('<a href="/reasoning">Reasoning and review</a>', prosthetic)
        self.assertIn('<a href="/prosthetics" aria-current="true">Prosthetics</a>', prosthetic)
