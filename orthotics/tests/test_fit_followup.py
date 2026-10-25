"""Tests for orthotics/fit.py (module 5) and the follow-up records orthotics module 6 keeps (shared/followup.py,
shared/dates.py): what the orthotist and the physiotherapist record, kept as written; the only thing worked out
is which review is due next."""

import json
import unittest

from orthotics.fit import BeforeAfter, CheckItem, FitRecord, TuningRow
from orthotics.plan import BACK_TO, OrthoticPlan, PlanError
from shared.dates import DateError, check_date
from shared.followup import Alert, FollowUp, MeasureDef, Visit, VisitStatus


class FitRecordTests(unittest.TestCase):
    def test_dates(self):
        self.assertEqual(check_date("2026-08-03"), "2026-08-03")
        self.assertIsNone(check_date(None))
        for bad in ("3 Aug", "2026-13-01", ""):
            with self.subTest(bad), self.assertRaises(DateError):
                check_date(bad)

    def test_round_trip_keeps_every_value_as_written(self):
        record = FitRecord(delivered_on="2026-08-03",
                           checkout=[CheckItem("Toes clear the floor in swing", True),
                                     CheckItem("Puts it on with one hand", False, "needs practice")],
                           tuning=[TuningRow("Tune 1", "5 mm heel wedge", "hyperextension reduced")],
                           measures=[BeforeAfter("Gait speed, 10-metre walk", "0.42 m/s", "0.53 m/s", "same cane")],
                           wearing=["Week 1: one hour, twice a day"], practice=["Sit to stand"],
                           training_by="physiotherapist", leaflet_ar="البس الجهاز مع حذائك.", leaflet_en="Wear it.",
                           leaflet_checked_by="an Arabic-reading orthotist")
        back = FitRecord.from_dict(json.loads(json.dumps(record.to_dict(), ensure_ascii=False)))
        self.assertEqual(back, record)
        self.assertIsInstance(back.checkout[1], CheckItem)
        self.assertEqual(back.checkout[1].note, "needs practice")

    def test_empty(self):
        self.assertTrue(FitRecord().empty)
        self.assertTrue(FitRecord.from_dict(None).empty)  # a plan saved before module 5
        self.assertFalse(FitRecord(training_by="physiotherapist").empty)
        with self.assertRaises(DateError):
            FitRecord(delivered_on="tomorrow")


class FollowUpTests(unittest.TestCase):
    def follow_up(self) -> FollowUp:
        return FollowUp(
            measures=[MeasureDef("Gait speed, 10-metre walk", "m/s", "same cane"), MeasureDef("Falls")],
            visits=[Visit("Delivery", "2026-08-03", "done", {"Gait speed, 10-metre walk": "0.42", "Falls": "2"}),
                    Visit("6-week review", "2026-09-14", VisitStatus.DONE, {"Gait speed, 10-metre walk": "0,61"},
                          wearing="about 6 h a day", device_condition="strap fraying"),
                    Visit("6-month review", None, "due"),
                    Visit("3-month review", "2026-11-02", "due")],
            alerts=[Alert("Redness at the lateral malleolus for 30 minutes", "fit")],
            due_next="device satisfaction questionnaire")

    def test_visit_status_and_date_are_checked(self):
        self.assertIs(Visit("x", status="due").status, VisitStatus.DUE)
        with self.assertRaises(ValueError):
            Visit("x", status="maybe")
        with self.assertRaises(DateError):
            Visit("x", date="next week")

    def test_an_alert_loops_back_only_to_an_orthotic_module(self):
        # The shared Alert keeps the module named; the orthotic plan says which modules an alert may name.
        self.assertEqual(BACK_TO, ("fit", "options", "analysis"))
        self.assertEqual(Alert("x", "options").back_to, "options")
        plan = OrthoticPlan(follow_up=FollowUp(alerts=[Alert("x", "options")]))
        self.assertEqual(OrthoticPlan.from_dict(plan.to_dict()), plan)
        with self.assertRaises(PlanError):
            OrthoticPlan(follow_up=FollowUp(alerts=[Alert("x", "manufacture")]))

    def test_the_next_review_is_the_earliest_dated_one_marked_due(self):
        follow = self.follow_up()
        self.assertEqual(follow.next_due().name, "3-month review")  # one without a date comes last
        follow.visits = [Visit("6-month review", None, "due")]
        self.assertEqual(follow.next_due().name, "6-month review")
        self.assertIsNone(FollowUp().next_due())

    def test_values_shown_as_entered_with_a_number_where_there_is_one(self):
        rows = self.follow_up().series("Gait speed, 10-metre walk")
        self.assertEqual([(v.name, number, raw) for v, number, raw in rows],
                         [("Delivery", 0.42, "0.42"), ("6-week review", 0.61, "0,61")])
        self.assertEqual([number for _, number, _ in FollowUp(visits=[Visit("x", values={"Falls": "none"})])
                          .series("Falls")], [None])  # not a number: shown as written, no chart value

    def test_the_latest_done_visit(self):
        self.assertEqual(self.follow_up().latest().name, "6-week review")
        self.assertIsNone(FollowUp(visits=[Visit("x", status="due")]).latest())

    def test_round_trip(self):
        follow = self.follow_up()
        data = json.loads(json.dumps(follow.to_dict()))
        self.assertEqual(data["visits"][0]["status"], "done")  # plain strings in the case file
        self.assertEqual(FollowUp.from_dict(data), follow)
        self.assertTrue(FollowUp.from_dict(None).empty)  # a plan saved before module 6


class OlderPlanTests(unittest.TestCase):
    def test_a_plan_saved_before_modules_5_and_6_reads_with_them_empty(self):
        # Case file version 3 (2026-10-23 morning): no fit, follow-up, conflicts, FES referral or simulation.
        old = {"requirements": [{"id": "R1", "text": "clear the toes", "findings": ["deviation.toe_drag"],
                                 "priority": "must"}],
               "options": [{"id": "A", "device": "hinged_afo", "parts": [{"part": "straps", "requirements": ["R1"]}],
                            "marks": {"R1": "yes"}, "notes": None}],
               "chosen": "A", "choice_reason": "knee control", "steps": {}, "parameter_versions": []}
        plan = OrthoticPlan.from_dict(old)
        self.assertEqual((plan.chosen, plan.requirements[0].text), ("A", "clear the toes"))
        self.assertTrue(plan.fit.empty)
        self.assertTrue(plan.follow_up.empty)
        self.assertEqual((plan.conflicts, plan.simulation, plan.option("A").costs), ([], [], []))


if __name__ == "__main__":
    unittest.main()
