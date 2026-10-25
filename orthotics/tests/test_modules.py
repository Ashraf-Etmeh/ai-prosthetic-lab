"""Tests for the orthotic modules after the analysis (2026-10-23): orthotics/plan.py, sources.py, modules.py.

Module 2 (requirements), module 3 (design options, materials and parts, the
orthotist's choice) and module 4 (the digital design workflow), the module map,
and the orthotic header on the review page. No embedding model and no AI: the
search is replaced by fixed passages, and the AI writer is the tests' fake.
"""

import json
import unittest
from unittest.mock import patch

from knowledge.retrieval import KnowledgeBaseMissing
from knowledge.tests.test_retrieval import make_store
from orthotics import sources
from orthotics.case import OrthoticExam, Walking
from orthotics.plan import (
    DesignOption,
    DeviceType,
    Method,
    OptionPart,
    OrthoticPlan,
    Part,
    PlanError,
    Step,
    StepRecord,
    StepStatus,
    case_findings,
)
from shared.requirements import Mark, Priority, Requirement
from orthotics.tests.helpers import OrthoticPageTestCase
from orthotics.tests.test_orthotics import full_case
from prosthetics.case import Case
from review.decision_log import LOG_VERSION, read_decisions
from shared.store import CaseRecord, CaseStore, store
from shared.testing import chunk_record, fake_embed, visible_text


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.case = full_case()
        self.findings = {f.key for f in case_findings(self.case)}

    def test_a_new_plan_starts_from_the_intake_lines(self):
        plan = OrthoticPlan.started_from(self.case)
        self.assertEqual([(r.id, r.text, r.findings, r.priority) for r in plan.requirements],
                         [("R1", "clear the toes in swing", [], None), ("R2", "control knee hyperextension", [], None)])

    def test_findings_are_what_the_case_recorded(self):
        keys = [f.key for f in case_findings(self.case)]
        self.assertEqual(keys[:2], ["deviation.toe_drag", "deviation.knee_hyperextension"])  # gait first
        self.assertIn("exam.dorsiflexion_knee_extended_deg", keys)
        self.assertIn("functional_goals", keys)
        empty = case_findings(full_case(walking=Walking(), exam=OrthoticExam(protective_sensation="unknown"),
                                        functional_goals=None, footwear=None, donning="unknown", body_weight_kg=None))
        self.assertEqual(empty, [])  # nothing recorded, and "unknown" is a gap, not a finding

    def test_requirements_are_checked_before_anything_changes(self):
        plan = OrthoticPlan.started_from(self.case)
        with self.assertRaises(PlanError):
            plan.set_requirements([Requirement("R1", "x", ["exam.shoe_size"])], self.findings)
        with self.assertRaises(PlanError):
            plan.set_requirements([Requirement("R1", "x"), Requirement("R1", "y")], self.findings)
        self.assertEqual(len(plan.requirements), 2)  # unchanged

    def test_a_removed_requirement_takes_its_marks_and_links(self):
        plan = OrthoticPlan.started_from(self.case)
        plan.set_options([DesignOption("A", DeviceType.SOLID_AFO, [OptionPart(Part.STRAPS, ["R1", "R2"])],
                                       {"R1": Mark.YES, "R2": Mark.NO})])
        plan.set_requirements([Requirement("R1", "clear the toes in swing")], self.findings)
        option = plan.option("A")
        self.assertEqual((option.marks, option.parts[0].requirements), ({"R1": Mark.YES}, ["R1"]))

    def test_options_choice_and_must_marks(self):
        plan = OrthoticPlan(requirements=[Requirement("R1", "knee control", priority=Priority.MUST)])
        with self.assertRaises(PlanError):
            plan.set_options([DesignOption("D", DeviceType.SOLID_AFO)])  # only A, B, C
        with self.assertRaises(PlanError):
            plan.set_options([DesignOption("A", DeviceType.SOLID_AFO, marks={"R9": Mark.YES})])
        plan.set_options([DesignOption("A", DeviceType.SOLID_AFO), DesignOption("B", DeviceType.CARBON_AFO,
                                                                                marks={"R1": Mark.NO})])
        self.assertEqual([r.id for r in plan.option("B").unaddressed(plan.requirements)], ["R1"])
        self.assertEqual(plan.option("A").unaddressed(plan.requirements), [])  # not marked is not "no"
        with self.assertRaises(PlanError):
            plan.choose("A", "  ")  # a choice needs its reason
        plan.choose("B", "lighter")
        plan.set_options([DesignOption("A", DeviceType.SOLID_AFO)])  # B removed: its choice goes with it
        self.assertEqual((plan.chosen, plan.choice_reason), (None, None))

    def test_a_changed_option_loses_its_choice(self):
        # The reason was written for one device and its parts; the same letter for another design must not keep it.
        plan = OrthoticPlan(requirements=[Requirement("R1", "knee control")])
        strap = OptionPart(Part.STRAPS)
        plan.set_options([DesignOption("A", DeviceType.SOLID_AFO, [strap]), DesignOption("B", DeviceType.FES)])
        plan.choose("A", "knee control in stance")
        plan.set_options([DesignOption("A", DeviceType.SOLID_AFO, [OptionPart(Part.STRAPS, ["R1"])],
                                       marks={"R1": Mark.YES}, notes="checked at fitting"),
                          DesignOption("B", DeviceType.FES)])
        self.assertEqual((plan.chosen, plan.choice_reason), ("A", "knee control in stance"))  # marks, notes, links
        for changed in (DesignOption("A", DeviceType.POSTERIOR_LEAF_SPRING, [strap]),  # another device
                        DesignOption("A", DeviceType.SOLID_AFO, [strap, OptionPart(Part.EVA_LINING)])):  # other parts
            with self.subTest(changed.device.value):
                plan.set_options([DesignOption("A", DeviceType.SOLID_AFO, [strap])])
                plan.choose("A", "knee control in stance")
                plan.set_options([changed])
                self.assertEqual((plan.chosen, plan.choice_reason), (None, None))

    def test_parameters_are_versions(self):
        plan = OrthoticPlan()
        plan.save_parameters({"ankle_angle": "5° plantarflexion", "lining": ""}, "first")
        plan.save_parameters({"ankle_angle": "3° plantarflexion"}, None)
        self.assertEqual([(v.number, v.values, v.note) for v in plan.parameter_versions],
                         [(1, {"ankle_angle": "5° plantarflexion"}, "first"), (2, {"ankle_angle": "3° plantarflexion"}, None)])
        with self.assertRaises(PlanError):
            plan.save_parameters({"ankle_angle": "3° plantarflexion"}, "same")
        with self.assertRaises(PlanError):
            plan.save_parameters({"colour": "blue"}, None)

    def test_a_step_takes_only_its_own_methods(self):
        plan = OrthoticPlan()
        with self.assertRaises(PlanError):
            plan.set_steps({Step.CAPTURE: StepRecord(StepStatus.DONE, Method.THERMOFORMING)})
        plan.set_steps({Step.CAPTURE: StepRecord(StepStatus.DONE, Method.SCAN_3D)})
        self.assertEqual(plan.step(Step.CAPTURE).method, Method.SCAN_3D)
        self.assertEqual(plan.step(Step.RELEASE).status, StepStatus.NOT_STARTED)

    def test_round_trip_through_a_case_file(self):
        plan = OrthoticPlan(requirements=[Requirement("R1", "clear the toes", ["deviation.toe_drag"], Priority.MUST)])
        plan.set_options([DesignOption("A", DeviceType.HINGED_AFO, [OptionPart(Part.EVA_LINING, ["R1"])],
                                       {"R1": Mark.PARTLY}, "bulkier")])
        plan.choose("A", "knee control")
        plan.set_steps({Step.CAPTURE: StepRecord(StepStatus.IN_PROGRESS, Method.PLASTER_CAST, "supine")})
        plan.save_parameters({"trim_lines": "below the fibular head"}, None)
        self.assertEqual(OrthoticPlan.from_dict(json.loads(json.dumps(plan.to_dict()))).to_dict(), plan.to_dict())


class SourcesTests(unittest.TestCase):
    def setUp(self):
        sources._cache.clear()
        self.addCleanup(sources._cache.clear)

    def store(self):
        return make_store(
            chunk_record("icrc-0001", "Preparation of the straps for the orthosis", domains=("orthotics",)),
            chunk_record("icrc-0002", "The proximal strap of the orthosis is riveted", domains=("orthotics",)),
            chunk_record("icrc-0003", "Another strap of the orthosis, the distal one", domains=("orthotics",)),
            chunk_record("other-0001", "Strap the orthosis over the shoe", domains=("orthotics",)),
            chunk_record("icrc-0004", "Contents 9 1.5 Straps 14 2.6 Strap 15 2.7 Strap of the orthosis",
                         domains=("orthotics",)),
            chunk_record("scoliosis_sosort_guidelines_2016-0001", "A brace strap for the orthosis",
                         domains=("orthotics",)),
            chunk_record("prosthetic-0001", "Strap of the socket of the orthosis", domains=("prosthetics",)),
        )

    def test_only_passages_that_mention_the_item(self):
        found = sources.find_passages({"part.straps": ("straps of the orthosis", r"\bstraps?\b"),
                                       "part.heel_wedge": ("heel wedge", r"wedge")},
                                      store=self.store(), embed=fake_embed)
        ids = [c.chunk_id for c in found["part.straps"]]
        self.assertEqual(found["part.heel_wedge"], [])  # nothing mentions it: the page says so
        self.assertLessEqual(len(ids), sources.PASSAGES_PER_ITEM)
        self.assertLessEqual(sum(1 for i in ids if i.startswith("icrc-")), sources.PER_DOCUMENT)
        self.assertNotIn("icrc-0004", ids)  # a table of contents
        self.assertNotIn("scoliosis_sosort_guidelines_2016-0001", ids)  # another condition
        self.assertNotIn("prosthetic-0001", ids)  # not an orthotic document
        self.assertIn("other-0001", ids)

    def test_a_search_is_done_once(self):
        store_, calls = self.store(), []

        def embed(texts):
            calls.append(texts)
            return fake_embed(texts)
        for _ in range(2):
            sources.find_passages({"part.straps": ("straps of the orthosis", r"strap")}, store=store_, embed=embed)
        self.assertEqual(len(calls), 1)

    def test_every_item_has_its_search(self):
        self.assertEqual(set(sources.DEVICES), set(DeviceType))
        self.assertEqual(set(sources.PARTS), set(Part))
        self.assertEqual(set(sources.STEPS), set(Step))


class ModulePageTests(OrthoticPageTestCase):
    def save_options(self, **extra):
        data = {"form": "options", "opt_A_device": "hinged_afo", "opt_A_mark_R1": "yes", "opt_A_part_1": "straps",
                "opt_A_part_1_req": "R1", "opt_A_notes": "bulkier at the ankle",
                "opt_B_device": "posterior_leaf_spring", "opt_B_mark_R1": "no", **extra}
        return self.client.post(self.url("options"), data=data)

    def test_the_map_names_the_briefs_capabilities(self):
        page = self.page("/orthotics")
        for name in ("تحليل الحالات الوظيفية", "اختيار وتصميم الأجهزة التقويمية", "ربط الحالة بالمكونات والمواد",
                     "دعم سير عمل التصميم الرقمي"):
            self.assertIn(name, page)
        self.assertIn("Not built yet", page)
        self.assertIn("الوحدات", self.page("/orthotics", "ar"))

    def test_the_review_page_leads_to_the_modules(self):
        page = self.client.get(f"/review/{self.case_id}").get_data(as_text=True)
        self.assertIn('class="ui-page"', page)
        self.assertIn(f'href="{self.url("requirements")}"', page)
        # The review step, reached from module 1 (the analysis page), is not module 1 itself.
        self.assertIn(f'href="{self.url("analysis")}">1 Analyse', page)
        self.assertNotIn('aria-current="page">', page)  # no module tab is current
        self.assertIn("What the sources say, and your review", visible_text(page))
        self.assertNotIn("Module 1", visible_text(page).split("What the sources say, and your review")[0])
        self.assertIn('href="/orthotics" aria-current="true">Orthotics', page)  # the domain switch
        # A prosthetic case's page: the same header, with the prosthetic modules (its own sections).
        prosthetic = self.client.post("/intake", data={"amputation_level": "transtibial", "side": "left"})
        page = self.client.get(prosthetic.headers["Location"]).get_data(as_text=True)
        self.assertIn('class="ui-page"', page)
        self.assertIn('href="/prosthetics" aria-current="true">Prosthetics', page)
        self.assertNotIn("/orthotics/", page)

    def test_requirements_tied_to_findings_with_a_priority(self):
        page = self.page(self.url("requirements"))
        # Written at intake: R1, in its row's text box for the orthotist to change (the design's requirement rows).
        self.assertIn('name="req_1_text" value="clear the toes in swing"',
                      self.client.get(self.url("requirements")).get_data(as_text=True))
        self.assertIn("Swing: toe drag", page)
        resp = self.client.post(self.url("requirements"), data={
            "rows": "2", "req_1_id": "R1", "req_1_text": "Clear the toes in swing", "req_1_priority": "must",
            "req_1_finding": ["deviation.toe_drag", "exam.dorsiflexion_knee_extended_deg"],
            "req_2_id": "", "req_2_text": "Can be put on with one hand"})
        self.assertEqual(resp.status_code, 302)
        plan = store.get(self.case_id).plan
        self.assertEqual([(r.id, r.text, r.priority) for r in plan.requirements],
                         [("R1", "Clear the toes in swing", Priority.MUST), ("R2", "Can be put on with one hand", None)])
        self.assertEqual(plan.requirements[0].findings, ["deviation.toe_drag", "exam.dorsiflexion_knee_extended_deg"])
        self.assertIn("ضروري", self.page(self.url("requirements"), "ar"))

    def test_a_refused_requirement_form_comes_back_as_sent(self):
        self.client.set_cookie("lang", "ar")
        resp = self.client.post(self.url("requirements"), data={"rows": "1", "req_1_text": "x" * 501,
                                                                "req_1_priority": "should"})
        self.assertEqual(resp.status_code, 400)
        page = resp.get_data(as_text=True)
        self.assertIn("حرفاً على الأكثر", visible_text(page))
        self.assertIn("x" * 501, page)
        self.assertIsNone(store.get(self.case_id).plan)  # nothing saved

    def test_options_side_by_side_with_parts_tied_to_the_case(self):
        self.client.post(self.url("requirements"), data={"rows": "1", "req_1_id": "R1", "req_1_text": "Clear the toes",
                                                         "req_1_priority": "must", "req_1_finding": "deviation.toe_drag"})
        self.assertEqual(self.save_options().status_code, 302)
        page = self.page(self.url("options"))
        self.assertLess(page.index("Option A"), page.index("Option B"))  # in the order written
        self.assertIn("Hinged AFO, ankle joints and plantarflexion stop", page)
        self.assertIn("Serves R1Clear the toes ← Swing: toe drag", page)  # part -> requirement -> finding
        self.assertIn("Marked by the orthotist as not addressing a Must requirement: R1 Clear the toes", page)
        self.assertIn("Preparation of the straps", page)  # the source's own words, quoted
        self.assertIn("Orthotic source (2024), p. 9", page)
        self.assertIn("No passage in the source library mentions this.", page)  # the device types found none
        self.assertIn("الخيار A", self.page(self.url("options"), "ar"))

    def test_an_option_without_a_device_is_refused(self):
        self.client.set_cookie("lang", "ar")
        resp = self.client.post(self.url("options"), data={"form": "options", "opt_C_notes": "KEEP-ME"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("اختر نوع جهازه", visible_text(resp.get_data(as_text=True)))
        self.assertIn("KEEP-ME", resp.get_data(as_text=True))

    def test_the_choice_is_logged_with_the_plan(self):
        self.save_options()
        resp = self.client.post(self.url("choice"), data={"form": "choice", "chosen": "A"})
        self.assertEqual(resp.status_code, 400)  # no reason
        self.assertIn("Write the reason for the choice.", visible_text(resp.get_data(as_text=True)))
        self.assertEqual(read_decisions(self.case_id), [])
        resp = self.client.post(self.url("choice"), data={"form": "choice", "chosen": "A", "reason": "knee control"})
        self.assertEqual(resp.status_code, 302)
        [entry] = read_decisions(self.case_id)
        self.assertEqual((entry["log_version"], entry["decision"], entry["note"]), (LOG_VERSION, "design_choice", "knee control"))
        self.assertEqual((entry["plan"]["chosen"], entry["plan"]["options"][0]["device"]), ("A", "hinged_afo"))
        self.assertIn("design choice", self.page(f"/review/{self.case_id}"))
        self.assertIn("Choices recorded (1)", self.page(self.url("options")))

    def test_the_design_workflow_and_parameter_versions(self):
        resp = self.client.post(self.url("design"), data={
            "action": "steps", "step_capture_status": "done", "step_capture_method": "scan_3d",
            "step_capture_notes": "ankle at the measured calf length", "step_rectify_status": "in_progress"})
        self.assertEqual(resp.status_code, 302)
        for value in ("5° plantarflexion", "3° plantarflexion"):
            resp = self.client.post(self.url("design"), data={"action": "parameters", "param_ankle_angle": value})
            self.assertEqual(resp.status_code, 302)
        resp = self.client.post(self.url("design"), data={"action": "parameters", "param_ankle_angle": "3° plantarflexion"})
        self.assertEqual(resp.status_code, 400)  # no change: no new version
        plan = store.get(self.case_id).plan
        self.assertEqual(plan.step(Step.CAPTURE).method, Method.SCAN_3D)
        self.assertEqual([v.values for v in plan.parameter_versions],
                         [{"ankle_angle": "5° plantarflexion"}, {"ankle_angle": "3° plantarflexion"}])
        page = self.page(self.url("design"))
        self.assertIn("Versions (2)", page)
        self.assertIn("3D scan", page)
        refused = self.client.post(self.url("design"), data={"action": "steps", "step_capture_method": "printing_3d"})
        self.assertEqual(refused.status_code, 400)  # not a capture method
        self.assertIn("دعم سير عمل التصميم الرقمي", page)  # the brief's name, next to the English heading
        self.assertIn("التصميم الرقمي", self.page(self.url("design"), "ar"))  # the Arabic page's own heading

    def test_nothing_here_calls_the_ai_and_the_plan_survives_a_restart(self):
        self.client.post(self.url("requirements"), data={"rows": "1", "req_1_id": "R1", "req_1_text": "Clear the toes"})
        self.save_options()
        self.client.post(self.url("design"), data={"action": "parameters", "param_trim_lines": "below the fibular head"})
        self.assertEqual(len(self.writer.calls), self.writer_calls)
        reopened = CaseStore(self.cases_dir).get(self.case_id)
        self.assertEqual(reopened.plan.to_dict(), store.get(self.case_id).plan.to_dict())

    def test_only_orthotic_cases(self):
        prosthetic = CaseRecord(case=Case(amputation_level="transtibial", side="left"))
        store.save(prosthetic)
        for page in ("requirements", "options", "design"):
            self.assertEqual(self.client.get(f"/orthotics/{prosthetic.case.case_id}/{page}").status_code, 404)
            self.assertEqual(self.client.get(f"/orthotics/no-such-case/{page}").status_code, 404)

    def test_without_the_library_the_page_says_so(self):
        with patch("orthotics.modules.find_passages", side_effect=KnowledgeBaseMissing("No vector store")):
            page = self.page(self.url("design"))
        self.assertIn("No vector store", page)


if __name__ == "__main__":
    unittest.main()
