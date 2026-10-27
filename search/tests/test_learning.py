"""Tests for case-based learning (search/learning.py, search/learning_routes.py; plan Part 7, use case 06).

Teaching cases, attempts, the learning log and the kept analyses go to temporary folders, never to the real
data/education/ or data/records/learning/ (except the first test, which only reads the drafts).
"""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from prosthetics.tests.helpers import ProstheticRouteTestCase
from search import learning
from shared import config
from shared.testing import visible_text

DRAFTS_DIR = config.TEACHING_CASES_DIR  # the real drafts, only read
DRAFTS = {case.id: case for case in learning.load_teaching_cases(DRAFTS_DIR)}


def raw_case(case_id: str) -> dict:
    return json.loads((DRAFTS_DIR / f"{case_id}.json").read_text(encoding="utf-8"))


PANEL = {"version": 1, "recorded_on": "2026-10-25", "members": 3,
         "missing": {"residual_limb.volume_stability": 2, "activity.k_level": 3, "residual_limb.pain": 0},
         "reasoning": ["Test reasoning in the member's own words."]}


class TeachingCaseTests(unittest.TestCase):
    def test_drafts_load_awaiting_the_educator(self):
        self.assertEqual(sorted(DRAFTS), ["TC-01", "TC-02", "TC-03"])
        for case in DRAFTS.values():
            with self.subTest(case=case.id):
                self.assertEqual(case.status, "draft")
                self.assertIsNone(case.level)  # the educator's
                self.assertIsNone(case.minutes)  # the educator's
                self.assertEqual(case.panel, ())  # no panel answers until the owner decides who sits on it
                self.assertEqual(case.domain, "prosthetics")
                self.assertIn("Awaiting the educator", case.note)
                self.assertEqual(case.case.case_id, case.id)
                self.assertIsNone(case.case.intake_notes)

    def check_refused(self, change):
        data = raw_case("TC-01")
        change(data)
        with self.assertRaises(learning.TeachingCaseError):
            learning.teaching_case_from_dict(data, "TC-01")

    def test_invalid_cases_refused(self):
        changes = {
            "version": lambda d: d.update(teaching_case_version=2),
            "id": lambda d: d.update(id="../x"),
            "status": lambda d: d.update(status="published"),
            "level": lambda d: d.update(level="expert"),
            "minutes 0": lambda d: d.update(minutes=0),
            "minutes too many": lambda d: d.update(minutes=learning.MAX_MINUTES + 1),
            "minutes text": lambda d: d.update(minutes="30"),
            "case": lambda d: d["case"].update(amputation_level="elbow"),
            "panel numbering": lambda d: d.update(panel=[{**PANEL, "version": 2}]),
            "panel item not a field": lambda d: d.update(panel=[{**PANEL, "missing": {"shoe_size": 1}}]),
            "panel count over members": lambda d: d.update(panel=[{**PANEL, "missing": {"activity.k_level": 4}}]),
            "panel date": lambda d: d.update(panel=[{**PANEL, "recorded_on": "25/10/2026"}]),
        }
        for name, change in changes.items():
            with self.subTest(name):
                self.check_refused(change)
        data = raw_case("TC-01")
        with self.assertRaises(learning.TeachingCaseError):  # the id must be the file's name
            learning.teaching_case_from_dict(data, "TC-09")

    def test_panel_versions(self):
        data = raw_case("TC-02")
        data.update(status="approved", level="intermediate", minutes=30,
                    panel=[PANEL, {**PANEL, "version": 2, "members": 4}])
        case = learning.teaching_case_from_dict(data, "TC-02")
        self.assertEqual((case.status, case.level, case.minutes), ("approved", "intermediate", 30))
        self.assertEqual(case.panel_now.version, 2)
        self.assertEqual(case.panel_now.members, 4)
        self.assertEqual(case.panel[0].missing["activity.k_level"], 3)


class LearningFolderTestCase(unittest.TestCase):
    """Teaching cases, attempts, the learning log and the analyses in a temporary folder."""

    def setUp(self):
        super().setUp()
        self.use_temporary_folders()

    def use_temporary_folders(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.learning_dir = Path(tmp.name) / "learning"
        self.teaching_dir = Path(tmp.name) / "teaching_cases"
        self.teaching_dir.mkdir()
        for name, value in (("LEARNING_DIR", self.learning_dir), ("TEACHING_CASES_DIR", self.teaching_dir)):
            patcher = patch.object(config, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def write_case(self, case_id: str, data: dict) -> None:
        (self.teaching_dir / f"{case_id}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


class UnitTests(unittest.TestCase):
    def test_units_come_from_the_field_names(self):
        from search.learning_routes import unit_key
        self.assertEqual(unit_key("body_weight_kg"), "learn_unit.kg")
        self.assertEqual(unit_key("age_years"), "learn_unit.years")
        self.assertEqual(unit_key("months_since_amputation"), "learn_unit.months")
        self.assertEqual(unit_key("months_since_onset"), "learn_unit.months")
        self.assertEqual(unit_key("ankle.dorsiflexion_knee_flexed_deg"), "learn_unit.deg")
        self.assertEqual(unit_key("walking.gait_speed_m_s"), "learn_unit.m_s")
        self.assertIsNone(unit_key("walking.falls_last_6_months"))  # a count, not a time
        self.assertIsNone(unit_key("residual_limb.pain"))


class LogTests(LearningFolderTestCase):
    def test_attempt_round_trip_and_bad_ids(self):
        attempt = learning.start_attempt("TC-01")
        self.assertEqual(attempt.done, ["read"])
        attempt.missing = ["cognitive_status"]
        learning.save_attempt(attempt)
        self.assertEqual(learning.get_attempt(attempt.id).missing, ["cognitive_status"])
        for bad in ("../log", "", "ABCDEF123456", "0" * 13):
            self.assertIsNone(learning.get_attempt(bad))

    def test_log_summary_and_cpd_record(self):
        self.assertEqual(learning.read_log(), [])
        case = DRAFTS["TC-01"]
        attempt = learning.start_attempt(case.id)
        attempt.reflection, attempt.minutes = "ما الذي تعلّمته", 25
        learning.log_attempt(attempt, case)
        learning.log_attempt(learning.start_attempt("TC-03"), DRAFTS["TC-03"])
        entries = learning.read_log()
        self.assertEqual(len(entries), 2)
        self.assertEqual((entries[0]["case_status"], entries[0]["level"], entries[0]["panel_version"]),
                         ("draft", None, None))
        self.assertEqual(learning.log_summary(entries),
                         {"cases": 2, "minutes": 25, "groups": {"transtibial": 1, "transradial": 1}})
        csv_text = learning.cpd_csv(entries)
        self.assertTrue(csv_text.startswith("﻿"))
        lines = csv_text.lstrip("﻿").splitlines()
        self.assertEqual(lines[0], ",".join(learning.CPD_COLUMNS))
        self.assertIn("TC-01,prosthetics,,25,ما الذي تعلّمته", lines[1])


class LearningRouteTests(ProstheticRouteTestCase, LearningFolderTestCase):
    def setUp(self):
        super().setUp()  # the app (RouteTestCase.setUp does not go on to LearningFolderTestCase.setUp)
        self.use_temporary_folders()
        for case_id in DRAFTS:
            self.write_case(case_id, raw_case(case_id))
        with_panel = copy.deepcopy(raw_case("TC-02"))
        with_panel.update(id="TC-P", status="approved", level="intermediate", minutes=30, panel=[PANEL])
        with_panel["case"]["case_id"] = "TC-P"
        self.write_case("TC-P", with_panel)

    def start(self, case_id: str) -> str:
        resp = self.client.post(f"/learn/{case_id}/start")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("step=read", resp.headers["Location"])
        return resp.headers["Location"].split("/learn/attempt/")[1].split("?")[0]

    def step(self, attempt_id: str, step: str, **data):
        url = f"/learn/attempt/{attempt_id}?step={step}"
        return self.client.post(url, data=data) if data else self.client.get(url)

    def work_to_compare(self, case_id: str, missing=("activity.k_level",), **options) -> str:
        attempt_id = self.start(case_id)
        resp = self.step(attempt_id, "missing", action="missing", missing=list(missing))
        self.assertEqual(resp.status_code, 302)
        resp = self.step(attempt_id, "options", action="options",
                         **{"options": "Option words.", "reasons": "Reason words.", **options})
        self.assertEqual(resp.status_code, 302)
        self.assertIn("step=compare", resp.headers["Location"])
        return attempt_id

    def test_library_in_both_languages(self):
        page = visible_text(self.client.get("/learn").get_data(as_text=True))
        for words in ("Case-based learning", "TC-01", "transtibial · left · vascular · 9 months since amputation",
                      "Draft, awaiting the educator", "Level not set yet", "Panel answers not recorded yet",
                      "Panel answers v1, 3 members", "Level: intermediate", "30 min", "No cases worked yet.",
                      "How learning stays honest", "Smart search"):
            self.assertIn(words, page)
        raw = self.client.get("/learn").get_data(as_text=True)
        self.assertNotIn('class="ui-casebar"', raw)
        self.assertIn('aria-current="page"', raw)
        self.client.set_cookie("lang", "ar")
        page = visible_text(self.client.get("/learn").get_data(as_text=True))
        self.client.delete_cookie("lang")
        for words in ("التعلّم بالحالات", "مسودة بانتظار المُدرِّب", "لم يُحدَّد المستوى بعد", "كيف يبقى التعلّم أميناً"):
            self.assertIn(words, page)

    def test_unknown_case_or_attempt(self):
        self.assertEqual(self.client.post("/learn/TC-99/start").status_code, 404)
        self.assertEqual(self.client.get("/learn/attempt/0123456789ab").status_code, 404)
        self.assertEqual(self.client.get("/learn/attempt/..%2Flog").status_code, 404)
        self.assertEqual(self.client.get("/learn/TC-01/start").status_code, 405)

    def test_read_step_shows_what_is_recorded(self):
        attempt_id = self.start("TC-03")
        page = visible_text(self.step(attempt_id, "read").get_data(as_text=True))
        for words in ("Read the case", "What is missing?", "Reflect and log", "transradial", "body-powered hook",
                      "return to carpentry work", "6 months", "45 years", "76 kg"):
            self.assertIn(words, page)
        self.assertNotIn("Residual limb sensation", page)  # not recorded: not listed

    def test_missing_step_refuses_an_unknown_item(self):
        attempt_id = self.start("TC-02")
        resp = self.step(attempt_id, "missing", action="missing", missing=["shoe_size"])
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(learning.get_attempt(attempt_id).missing, [])
        resp = self.step(attempt_id, "missing", action="missing", missing=["activity.k_level"],
                         other_missing="x" * (learning.MAX_TEXT + 1))
        self.assertEqual(resp.status_code, 400)
        self.assertIn(f"at most {learning.MAX_TEXT} characters", resp.get_data(as_text=True))

    def test_options_are_needed(self):
        attempt_id = self.start("TC-02")
        self.step(attempt_id, "missing", action="missing", missing=["activity.k_level"])
        resp = self.step(attempt_id, "options", action="options", options="  ", reasons="why")
        self.assertEqual(resp.status_code, 400)
        page = resp.get_data(as_text=True)
        self.assertIn("Write the options you would weigh before comparing.", page)
        self.assertIn(">why</textarea>", page)  # what was typed stays in the form

    def test_compare_waits_for_the_earlier_steps(self):
        attempt_id = self.start("TC-02")
        page = self.step(attempt_id, "compare").get_data(as_text=True)
        self.assertIn('name="action" value="missing"', page)
        self.assertEqual(self.writer.calls, [])  # no analysis yet
        resp = self.step(attempt_id, "reflect", action="reflect", reflection="r", minutes="10")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Look at the comparison before adding the case to your log.", resp.get_data(as_text=True))
        self.assertEqual(learning.read_log(), [])

    def test_compare_without_panel(self):
        attempt_id = self.work_to_compare("TC-02")
        page = visible_text(self.step(attempt_id, "compare").get_data(as_text=True))
        self.assertIn("Not recorded yet", page)  # the panel column
        self.assertIn("The educator has not recorded the panel's answers for this case yet", page)
        self.assertIn("Test Guideline (2024), p. 14", page)  # the source for the volume gap
        self.assertIn("What the sources say about an item you did not mark: Residual limb volume stability", page)
        self.assertIn("Residual limb volume should be stable", page)  # the checked quote
        self.assertIn("Option words.", page)
        self.assertNotIn("You marked", page)  # nothing to count against
        # A gap without a passage is said once, in the table, not listed again below it
        self.assertNotIn("an item you did not mark: Body weight", page)
        self.assertNotIn("correct", page.lower())

    def test_compare_with_panel_counts_only(self):
        attempt_id = self.work_to_compare("TC-P", missing=("activity.k_level", "cognitive_status"))
        page = visible_text(self.step(attempt_id, "compare").get_data(as_text=True))
        self.assertIn("You marked 1 of the 2 items the panel marked", page)
        self.assertIn("2 of 3 marked it", page)  # volume stability
        self.assertIn("3 of 3 marked it", page)  # K-level
        self.assertIn("No member marked it", page)  # cognitive status: the learner's only
        self.assertIn("Recorded in the case", page)  # cognitive status is recorded in TC-02
        self.assertIn("Test reasoning in the member's own words.", page)
        self.assertIn("version 1, recorded 2026-10-25", page)
        self.assertNotIn("correct", page.lower())

    def test_analysis_runs_once_and_sends_only_level_side_k_level(self):
        attempt_id = self.work_to_compare("TC-03", missing=("comorbidities",))
        self.step(attempt_id, "compare")
        calls = len(self.writer.calls)
        self.assertGreater(calls, 0)
        self.step(attempt_id, "compare")
        second = self.work_to_compare("TC-03")
        self.step(second, "compare")
        self.assertEqual(len(self.writer.calls), calls)  # kept, not run again
        self.assertTrue((self.learning_dir / "analysis" / "TC-03.json").is_file())
        for _, user, _ in self.writer.calls:
            for typed in ("carpentry", "harness discomfort", "right hand"):
                self.assertNotIn(typed, user)

    def test_reflect_and_log(self):
        attempt_id = self.work_to_compare("TC-P")
        self.step(attempt_id, "compare")
        resp = self.step(attempt_id, "reflect", action="reflect", reflection="Next time ask first.", minutes="0")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Minutes must be a whole number from 1 to 600", resp.get_data(as_text=True))
        resp = self.step(attempt_id, "reflect", action="reflect", reflection="Next time ask first.", minutes="40")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("logged=1", resp.headers["Location"])
        [entry] = learning.read_log()
        self.assertEqual((entry["case_id"], entry["case_status"], entry["level"], entry["panel_version"]),
                         ("TC-P", "approved", "intermediate", 1))
        self.assertEqual(entry["attempt"]["minutes"], 40)
        self.assertEqual(entry["attempt"]["done"], ["read", "missing", "options", "compare", "reflect"])
        page = visible_text(self.client.get(resp.headers["Location"]).get_data(as_text=True))
        self.assertIn("The case is in your learning log.", page)
        self.assertIn("0.7", page)  # 40 minutes in hours
        self.assertIn("Export the CPD record (CSV)", page)
        csv_resp = self.client.get("/learn/log.csv")
        self.assertEqual(csv_resp.mimetype, "text/csv")
        self.assertIn("attachment", csv_resp.headers["Content-Disposition"])
        self.assertIn("TC-P,prosthetics,intermediate,40,Next time ask first.", csv_resp.get_data(as_text=True))

    def test_steps_in_arabic(self):
        attempt_id = self.work_to_compare("TC-P")
        self.client.set_cookie("lang", "ar")
        pages = {step: visible_text(self.step(attempt_id, step).get_data(as_text=True))
                 for step in learning.STEPS}
        self.client.delete_cookie("lang")
        self.assertIn("اقرأ الحالة", pages["read"])
        self.assertIn("ما المعلومات التي تريدها قبل أن تقرّر؟", pages["missing"])
        self.assertIn("الخيارات التي ستوازن بينها، ولماذا", pages["options"])
        self.assertIn("ليس تقييماً", pages["compare"])
        self.assertIn("أضف إلى سجل التعلّم", pages["reflect"])


if __name__ == "__main__":
    unittest.main()
