"""Tests for the orthotic pages added from the design's screens on 2026-10-23: module 1 (analysis), module 5
(fit, tune and train, and the leaflet), the fabrication sheet, module 6 (follow-up) and the summary for the
physiotherapist. Each page in English and Arabic, each form saved and refused; every value is the orthotist's,
nothing is sent to the AI, and a case file or log line from before these pages still reads."""

import json
import unittest

from orthotics.tests.helpers import OrthoticPageTestCase
from review.decision_log import read_decisions
from shared.store import CaseStore, store

LEAFLET_AR = "البس الجهاز دائماً مع حذائك الرياضي المغلق."


class AnalysisPageTests(OrthoticPageTestCase):
    def test_the_form_leads_to_the_case_analysis(self):
        page = self.page(self.url("analysis"))
        for text in ("Module 1", "Functional case analysis", "Goals, by ICF level", "Structured exam",
                     "Gait, observed phase by phase", "Information needed", "Continue to requirements →"):
            self.assertIn(text, page)
        self.assertIn("-5°", page)  # recorded at intake, shown as entered
        self.assertIn("toe drag", page.lower())
        self.assertIn("تحليل الحالات الوظيفية", page)  # the brief's own name, next to the English heading
        self.assertIn("تحليل الحالة الوظيفية", self.page(self.url("analysis"), "ar"))

    def test_it_links_to_the_review_and_to_re_assess(self):
        html = self.client.get(self.url("analysis")).get_data(as_text=True)
        self.assertIn(f'href="/review/{self.case_id}"', html)
        self.assertIn(f'href="/intake/orthotics?case={self.case_id}"', html)
        self.assertIn('aria-current="page">1 Analyse', html)  # this page is module 1


class FitPageTests(OrthoticPageTestCase):
    def test_each_part_of_the_fit_record_is_saved_as_written(self):
        posts = [
            {"action": "delivered", "delivered_on": "2026-08-03"},
            {"action": "checkout", "check_rows": "1", "check_1_text": "Toes clear the floor in swing", "check_1_done": "on"},
            {"action": "tuning", "tune_rows": "1", "tune_1_step": "Tune 1", "tune_1_change": "5 mm heel wedge",
             "tune_1_seen": "Hyperextension reduced"},
            {"action": "measures", "ba_rows": "1", "ba_1_measure": "Gait speed, 10-metre walk", "ba_1_before": "0.42 m/s",
             "ba_1_after": "0.53 m/s", "ba_1_note": "same cane"},
            {"action": "training", "wearing": "Week 1: one hour, twice a day\nWeek 2: half the day",
             "practice": "Sit to stand", "training_by": "physiotherapist"},
            {"action": "leaflet", "leaflet_ar": LEAFLET_AR, "leaflet_en": "Always wear it with your closed trainers."},
        ]
        for data in posts:
            with self.subTest(data["action"]):
                self.assertEqual(self.post("fit", **data).status_code, 302)
        fit = store.get(self.case_id).plan.fit
        self.assertEqual(fit.delivered_on, "2026-08-03")
        self.assertEqual([(c.text, c.done) for c in fit.checkout], [("Toes clear the floor in swing", True)])
        self.assertEqual((fit.tuning[0].change, fit.measures[0].after), ("5 mm heel wedge", "0.53 m/s"))
        self.assertEqual(fit.wearing, ["Week 1: one hour, twice a day", "Week 2: half the day"])
        page = self.page(self.url("fit"))
        for text in ("Fit, tune and train", "5 mm heel wedge", "Hyperextension reduced", "0.53 m/s", "Sit to stand",
                     LEAFLET_AR):
            self.assertIn(text, page)
        self.assertIn("التركيب والضبط والتدريب", self.page(self.url("fit"), "ar"))
        self.assertEqual(len(self.writer.calls), self.writer_calls)  # nothing here asks the AI

    def test_the_checkout_starts_from_the_orthotists_own_words(self):
        page = self.page(self.url("fit"))
        self.assertIn("R1 clear the toes in swing", self.client.get(self.url("fit")).get_data(as_text=True))
        self.assertIn("Starting from the chosen option's checks at fitting and the requirements", page)
        self.assertIsNone(store.get(self.case_id).plan)  # only shown: nothing saved until the orthotist saves

    def test_refused_forms_come_back_as_sent(self):
        resp = self.post("fit", "ar", action="delivered", delivered_on="3 Aug")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("أدخل تاريخاً", resp.get_data(as_text=True))
        resp = self.post("fit", action="leaflet", leaflet_ar="x" * 3001)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("at most 3000 characters", resp.get_data(as_text=True))
        self.assertEqual(self.post("fit", action="something else").status_code, 400)
        self.assertIsNone(store.get(self.case_id).plan)  # nothing saved


class LeafletTests(OrthoticPageTestCase):
    def test_the_leaflet_in_each_language_and_the_unchecked_warning(self):
        self.post("fit", action="leaflet", leaflet_ar=LEAFLET_AR, leaflet_en="Always wear it with your trainers.")
        arabic = self.page(self.url("leaflet") + "?lang=ar")
        self.assertIn(LEAFLET_AR, arabic)
        self.assertIn("The Arabic text has not been checked by an Arabic-reading orthotist yet", arabic)
        self.assertIn("Always wear it with your trainers.", self.page(self.url("leaflet") + "?lang=en"))
        self.post("fit", action="leaflet", leaflet_ar=LEAFLET_AR, leaflet_checked_by="an Arabic-reading orthotist")
        self.assertNotIn("has not been checked", self.page(self.url("leaflet") + "?lang=ar"))
        self.assertEqual(self.client.get(self.url("leaflet") + "?lang=fr").status_code, 404)

    def test_the_next_review_comes_from_the_follow_up_visits(self):
        self.post("follow-up", action="visits", visit_rows="1", visit_1_name="3-month review",
                  visit_1_date="2026-11-02", visit_1_status="due")
        self.assertIn("موعد المراجعة القادم: 2026-11-02", self.page(self.url("leaflet") + "?lang=ar"))
        self.assertIn("Next review: 2026-11-02", self.page(self.url("leaflet") + "?lang=en"))


class FabricationSheetTests(OrthoticPageTestCase):
    def test_before_a_choice_and_after(self):
        self.assertIn("No option chosen yet.", self.page(self.url("fabrication-sheet")))
        self.post("options", form="options", opt_A_device="hinged_afo", opt_A_part_1="straps")
        self.post("choice", form="choice", chosen="A", reason="knee control")
        self.post("design", action="parameters", param_ankle_angle="5° plantarflexion")
        page = self.page(self.url("fabrication-sheet"))
        for text in ("Fabrication sheet", "Option A", "Hinged AFO, ankle joints and plantarflexion stop",
                     "Straps and closure", "5° plantarflexion", "Not every parameter is approved yet."):
            self.assertIn(text, page)
        self.assertIn("ورقة التصنيع", self.page(self.url("fabrication-sheet"), "ar"))


class FollowUpPageTests(OrthoticPageTestCase):
    def set_up_follow_up(self):
        for data in ({"action": "measures", "measure_rows": "1", "measure_1_name": "Gait speed, 10-metre walk",
                      "measure_1_unit": "m/s", "measure_1_how": "same cane", "due_next": "device satisfaction"},
                     {"action": "visits", "visit_rows": "2", "visit_1_name": "Delivery", "visit_1_date": "2026-08-03",
                      "visit_1_status": "done", "visit_1_value_1": "0.42", "visit_1_wearing": "about 6 h a day",
                      "visit_2_name": "3-month review", "visit_2_date": "2026-11-02", "visit_2_status": "due"},
                     {"action": "alerts", "alert_rows": "1", "alert_1_text": "Redness at the lateral malleolus",
                      "alert_1_back_to": "fit"}):
            self.assertEqual(self.post("follow-up", **data).status_code, 302, data["action"])

    def test_measures_visits_and_alerts_shown_as_recorded(self):
        self.set_up_follow_up()
        follow = store.get(self.case_id).plan.follow_up
        self.assertEqual(follow.visits[0].values, {"Gait speed, 10-metre walk": "0.42"})
        self.assertEqual(follow.next_due().name, "3-month review")
        page = self.page(self.url("follow-up"))
        for text in ("Follow-up", "Gait speed, 10-metre walk", "0.42", "Redness at the lateral malleolus",
                     "Adjust in fit and tune →", "about 6 h a day", "Loop back"):
            self.assertIn(text, page)
        html = self.client.get(self.url("follow-up")).get_data(as_text=True)
        self.assertIn(f'href="{self.url("fit")}"', html)  # the alert loops back to module 5
        self.assertIn("المتابعة", self.page(self.url("follow-up"), "ar"))
        self.assertEqual(len(self.writer.calls), self.writer_calls)

    def test_a_removed_measure_takes_its_values_with_it(self):
        self.set_up_follow_up()
        self.post("follow-up", action="measures", measure_rows="1", measure_1_name="Berg Balance Scale")
        self.assertEqual(store.get(self.case_id).plan.follow_up.visits[0].values, {})

    def test_refused_forms(self):
        for data, message in (
                ({"action": "visits", "visit_rows": "1", "visit_1_wearing": "6 h"}, "A visit with values needs its name."),
                ({"action": "visits", "visit_rows": "1", "visit_1_name": "x", "visit_1_date": "soon"}, "enter a date"),
                ({"action": "measures", "measure_rows": "1", "measure_1_unit": "m/s"}, "A measure needs its name."),
                ({"action": "alerts", "alert_rows": "1", "alert_1_back_to": "fit"}, "An alert needs its text."),
                ({"action": "alerts", "alert_rows": "1", "alert_1_text": "x", "alert_1_back_to": "manufacture"}, None)):
            with self.subTest(data):
                resp = self.post("follow-up", **data)
                self.assertEqual(resp.status_code, 400)
                if message:
                    self.assertIn(message, resp.get_data(as_text=True))
        self.assertIsNone(store.get(self.case_id).plan)
        resp = self.post("follow-up", "ar", action="measures", measure_rows="1", measure_1_unit="m/s")
        self.assertIn("يحتاج المقياس إلى اسمه.", resp.get_data(as_text=True))


class SummaryTests(OrthoticPageTestCase):
    def test_the_summary_for_the_physiotherapist(self):
        self.post("follow-up", action="measures", measure_rows="1", measure_1_name="Gait speed, 10-metre walk")
        self.post("follow-up", action="visits", visit_rows="1", visit_1_name="Delivery", visit_1_date="2026-08-03",
                  visit_1_status="done", visit_1_value_1="0.42")
        self.post("fit", action="training", wearing="Week 1: one hour", practice="Sit to stand")
        page = self.page(self.url("summary"))
        for text in ("Summary for the physiotherapist", self.case_id, "Sit to stand", "0.42"):
            self.assertIn(text, page)
        self.assertIn("ملخص لأخصائي العلاج الطبيعي", self.page(self.url("summary"), "ar"))


class OlderRecordsTests(OrthoticPageTestCase):
    def test_a_case_file_and_a_log_line_from_before_these_pages(self):
        # Case file version 3 (2026-10-23 morning): no goals by ICF level, "how measured", ulcer check, fit or follow-up.
        old_case = {"domain": "orthotics", "case_id": "old0rth0c4se", "created_at": "2026-10-23T08:00:00+00:00",
                    "condition": "stroke", "side": "left", "months_since_onset": 7, "functional_goals": None,
                    "walking": {"deviations": ["toe_drag"]}, "exam": {"dorsiflexion_knee_extended_deg": -5}}
        old_plan = {"requirements": [{"id": "R1", "text": "clear the toes", "findings": ["deviation.toe_drag"],
                                      "priority": "must"}],
                    "options": [{"id": "A", "device": "hinged_afo", "parts": [], "marks": {"R1": "yes"}, "notes": None}],
                    "chosen": "A", "choice_reason": "knee control", "steps": {}, "parameter_versions": []}
        self.cases_dir.mkdir(parents=True, exist_ok=True)
        (self.cases_dir / "old0rth0c4se.json").write_text(json.dumps(
            {"case_file_version": 3, "case": old_case, "knowledge_warning": None, "retrieved_chunks": {}, "gaps": [],
             "generation": None, "plan": old_plan}), encoding="utf-8")
        record = CaseStore(self.cases_dir).get("old0rth0c4se")
        self.assertTrue(record.plan.fit.empty)
        # A design choice logged with LOG_VERSION 8 (before the FES referral and the option cards' new keys).
        line = {"log_version": 8, "timestamp": "2026-10-23T08:30:00+00:00", "case_id": "old0rth0c4se",
                "decision": "design_choice", "note": "knee control", "domain": "orthotics", "plan": old_plan}
        self.log_path.write_text(json.dumps(line) + "\n", encoding="utf-8")
        self.assertEqual([e["log_version"] for e in read_decisions("old0rth0c4se", path=self.log_path)], [8])
        for page in ("analysis", "requirements", "options", "design", "fabrication-sheet", "fit", "leaflet",
                     "follow-up", "summary"):
            with self.subTest(page):
                resp = self.client.get(f"/orthotics/old0rth0c4se/{page}")
                self.assertEqual(resp.status_code, 200)
        self.assertIn("Choices recorded (1)", self.page("/orthotics/old0rth0c4se/options"))


if __name__ == "__main__":
    unittest.main()
