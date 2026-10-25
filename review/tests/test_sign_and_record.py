"""Tests for "sign and record" (review log version 11, plan Part 4, 2026-10-25; SYSTEM_DESIGN.md §7.2): the mark
"summary is wrong", a reason kept with a gap's mark, a decision that must be chosen, and the versions each
decision is signed with."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from knowledge.library import library_version
from prosthetics.tests.helpers import ProstheticRouteTestCase
from review.decision_log import LOG_VERSION, MAX_REASON, InvalidDecision, read_decisions, record_decision
from review.routes import judgement_summary
from review.tests.test_decision_log import VOLUME, WOUND, make_record
from shared.store import store
from shared.testing import visible_text


class LogVersion11Tests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "review_log.jsonl"
        self.record = make_record()

    def gap(self, entry, field):
        return next(g for g in entry["gaps"] if g["field"] == field)

    def test_a_reason_is_kept_with_its_gap(self):
        entry = record_decision(self.record, "approve", gap_judgements={VOLUME: "not_needed"},
                                gap_reasons={VOLUME: "  measured last week  ", WOUND: " "}, path=self.path)
        self.assertEqual(entry["log_version"], LOG_VERSION)
        self.assertEqual(self.gap(entry, VOLUME)["reviewer_reason"], "measured last week")
        self.assertIsNone(self.gap(entry, WOUND)["reviewer_reason"])  # an empty reason is none

    def test_a_reason_for_another_gap_or_too_long_is_refused(self):
        for reasons in ({"not.a.gap": "x"}, {VOLUME: "x" * (MAX_REASON + 1)}):
            with self.subTest(reasons=list(reasons)), self.assertRaises(InvalidDecision):
                record_decision(self.record, "approve", gap_reasons=reasons, path=self.path)
        self.assertEqual(read_decisions(path=self.path), [])

    def test_a_decision_must_be_chosen(self):
        with self.assertRaises(InvalidDecision) as refused:
            record_decision(self.record, "", path=self.path)
        self.assertEqual(refused.exception.key, "error.choose_decision")

    def test_each_decision_is_signed_with_its_versions(self):
        entry = record_decision(self.record, "reject", note="wrong case", path=self.path)
        self.assertEqual(entry["versions"], {"prompt": None, "models": [], "library": library_version()})
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["versions"], entry["versions"])

    def test_older_lines_still_read_and_summarise(self):
        old = {"log_version": 10, "logged_at": "2026-10-24T10:00:00+00:00", "case_id": "case-a", "decision": "edit",
               "note": "n", "gaps": [{"field": VOLUME, "reviewer_judgement": "needed"}],
               "components": {"sections": [{"component": "knee", "statements": [
                   {"id": "s1", "reviewer_judgement": "relevant"}]}]}}
        self.path.write_text(json.dumps(old) + "\n", encoding="utf-8")
        [entry] = read_decisions(path=self.path)
        self.assertEqual(judgement_summary(entry), "1 needed; components: 1 relevant")
        entry["components"]["sections"][0]["statements"].append({"id": "s2", "reviewer_judgement": "summary_wrong"})
        self.assertEqual(judgement_summary(entry), "1 needed; components: 1 relevant, 1 summary wrong")


class SignAndRecordPageTests(ProstheticRouteTestCase):
    """The review page of a transfemoral case (the fake search gives its knee a statement with an AI summary)."""

    def setUp(self):
        super().setUp()
        resp = self.post_intake(amputation_level="transfemoral", k_level="K3")
        self.case_id = resp.headers["Location"].rsplit("/", 1)[-1]
        self.record = store.get(self.case_id)
        self.statement = self.record.shown_statements()[0].statement.id
        self.gap_field = self.record.gaps[0].field

    def page(self, lang="en"):
        self.client.set_cookie("lang", lang)
        return self.client.get(f"/review/{self.case_id}").get_data(as_text=True)

    def test_the_page_offers_the_three_marks_a_reason_and_one_sign_button(self):
        html = self.page()
        self.assertIn(f'name="opt:{self.statement}" value="summary_wrong"', html)
        self.assertIn(f'name="why:{self.gap_field}"', html)
        for value in ("approve", "edit", "reject"):
            self.assertIn(f'name="decision" value="{value}"', html)
        text = visible_text(html)
        for shown in ("Approve as reviewed", "Approve with edits", "Reject the analysis", "Sign and record",
                      "Summary is wrong", "Why (kept with the case)",
                      "Recorded once, never edited: the case, every item as shown"):
            self.assertIn(shown, text)
        arabic = visible_text(self.page("ar"))
        for shown in ("اعتماد كما رُوجع", "وقّع وسجّل", "الملخص خاطئ"):
            self.assertIn(shown, arabic)

    def test_sign_and_record_logs_the_marks_the_reason_and_the_versions(self):
        resp = self.client.post(f"/review/{self.case_id}/decision", data={
            "decision": "approve", f"opt:{self.statement}": "summary_wrong", f"gap:{self.gap_field}": "not_needed",
            f"why:{self.gap_field}": "assessed by the team last month"})
        self.assertEqual(resp.status_code, 302)
        [entry] = read_decisions(self.case_id)
        marks = {s["id"]: s["reviewer_judgement"] for part in ("components", "fitting")
                 for section in entry[part]["sections"] for s in section["statements"]}
        self.assertEqual(marks[self.statement], "summary_wrong")
        gap = next(g for g in entry["gaps"] if g["field"] == self.gap_field)
        self.assertEqual((gap["reviewer_judgement"], gap["reviewer_reason"]),
                         ("not_needed", "assessed by the team last month"))
        self.assertEqual(entry["versions"]["models"], ["fake-model"])
        self.assertTrue(entry["versions"]["prompt"])
        self.assertIn("1 summary wrong", visible_text(self.client.get(resp.headers["Location"]).get_data(as_text=True)))

    def test_without_a_decision_nothing_is_logged_and_the_marks_stay(self):
        resp = self.client.post(f"/review/{self.case_id}/decision", data={
            f"opt:{self.statement}": "summary_wrong", f"why:{self.gap_field}": "kept as typed"})
        self.assertEqual(resp.status_code, 400)
        html = resp.get_data(as_text=True)
        self.assertIn("Choose approve as reviewed, approve with edits or reject the analysis.", visible_text(html))
        self.assertIn('value="summary_wrong" checked', html)
        self.assertIn('value="kept as typed"', html)
        self.assertEqual(read_decisions(self.case_id), [])

    def test_the_page_names_the_library_build_it_is_signed_with(self):
        with patch("review.routes.library_version", return_value={"built": "2026-10-22T19:01:20+00:00",
                                                                     "passages": 4890}):
            self.assertIn("Source library built 2026-10-22, 4890 passages", visible_text(self.page()))


if __name__ == "__main__":
    unittest.main()
