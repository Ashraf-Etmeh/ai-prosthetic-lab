"""Tests for the prosthetic module pages (plan Part 3, 2026-10-24): prosthetics/plan.py, hard_stops.py, modules.py.

Every value on these pages is the prosthetist's: the tests check that what is typed
is kept as typed, that nothing is ranked, chosen or judged by the code, that the
draft hard stops only read what was recorded, and that nothing typed reaches the AI.
"""

import json
import unittest

from prosthetics import hard_stops
from prosthetics.case import Case, ResidualLimb
from prosthetics.plan import (
    Assessment,
    ComponentOption,
    FittingStep,
    Observation,
    ProstheticPlan,
    StepRecord,
    case_findings,
    components_for,
    linkable,
    missing_findings,
    waiting_on,
)
from prosthetics.tests.helpers import FULL_FORM, ProstheticRouteTestCase
from review.decision_log import LOG_VERSION, read_decisions
from shared.case_schema import YesNoUnknown
from shared.fitting import StepStatus
from shared.followup import Alert, FollowUp
from shared.requirements import Conflict, Mark, PlanError, Priority, Requirement
from shared.store import record_from_dict, record_to_dict, store
from shared.testing import visible_text


def tt_case(**limb) -> Case:
    return Case(amputation_level="transtibial", side="left", residual_limb=ResidualLimb(**limb))


def option(option_id: str, name: str, **fields) -> ComponentOption:
    return ComponentOption(option_id, name, **fields)


# ---- The plan ---------------------------------------------------------------------


class PlanTests(unittest.TestCase):
    def test_the_components_are_the_answer_keys_for_the_level(self):
        self.assertEqual(components_for(tt_case()), ("foot_ankle", "socket", "interface", "suspension"))
        self.assertEqual(components_for(Case(amputation_level="transfemoral", side="left"))[0], "knee")
        self.assertEqual(components_for(Case(amputation_level="transradial", side="left")),
                         ("prosthesis_type", "control_and_fit"))

    def test_a_filled_plan_reads_back_as_saved(self):
        plan = ProstheticPlan(
            assessment=Assessment(measured_how={"residual_limb.wound_status": "inspection"}, joint_range="full",
                                  infection="no", other_foot_neuropathy="yes", mobility=[{"name": "2MWT", "value": "112 m"}]),
            requirements=[Requirement("R1", "change walking speed", ["activity.k_level"], "must"),
                          Requirement("R2", "comfortable when standing long")],
            conflicts=[Conflict("R1", "R2", "speed against comfort")],
            options={"foot_ankle": [option("A", "Energy-storing foot", marks={"R1": "yes"}, weight_limit_kg=100,
                                           costs=["stiffer on slopes"])]},
            configuration={"foot_ankle": "A"}, choice_reason="volume still changing",
            steps={"check_socket": StepRecord("done", "v2 approved")},
            observations=[Observation("dynamic_alignment", "knee stays straight", "loading_response", "foot 5 mm back")],
            follow_up=FollowUp(alerts=[Alert("sock ply rising", "fitting")]),
        )
        plan.add_socket_version("redness at the fibular head", "relief")
        plan.save_alignment({"Foot position": "5 mm posterior"}, "after walking", "prosthetist")
        data = json.loads(json.dumps(plan.to_dict()))  # as in a case file
        self.assertEqual(ProstheticPlan.from_dict(data).to_dict(), plan.to_dict())
        self.assertIs(ProstheticPlan.from_dict(data).assessment.infection, YesNoUnknown.NO)

    def test_options_are_checked_before_they_are_kept(self):
        plan = ProstheticPlan(requirements=[Requirement("R1", "x")])
        components = components_for(tt_case())
        for options, sources in (([option("A", "a"), option("A", "b")], set()),  # one id twice
                                 ([option("D", "a")], set()),  # not A, B or C
                                 ([option("A", " ")], set()),  # no name
                                 ([option("A", "a", marks={"R9": "yes"})], set()),  # not a requirement
                                 ([option("A", "a", sources=["s1"])], set())):  # a source the page didn't show
            with self.subTest(options=options), self.assertRaises(PlanError):
                plan.set_options("foot_ankle", options, components, sources)
        with self.assertRaises(PlanError):
            plan.set_options("knee", [option("A", "a")], components, set())  # no knee below the knee
        with self.assertRaises(ValueError):
            ComponentOption("A", "a", weight_limit_kg=-1)  # the form refuses it first, in its own words
        self.assertEqual(plan.options, {})

    def test_the_choice_goes_when_a_chosen_option_is_renamed_or_removed(self):
        components = components_for(tt_case())
        plan = ProstheticPlan(requirements=[Requirement("R1", "x")])
        plan.set_options("foot_ankle", [option("A", "carbon foot"), option("B", "multiaxial foot")], components, set())
        plan.set_options("socket", [option("A", "TSB")], components, set())
        with self.assertRaises(PlanError):
            plan.choose({"foot_ankle": "A"}, " ")  # a reason is needed
        with self.assertRaises(PlanError):
            plan.choose({"foot_ankle": "C"}, "why")  # no such option
        with self.assertRaises(PlanError):
            plan.choose({}, "why")  # at least one option
        plan.choose({"foot_ankle": "A", "socket": "A", "interface": ""}, "why")
        self.assertEqual(plan.chosen, {"foot_ankle": "A", "socket": "A"})
        # New marks or costs keep it.
        plan.set_options("foot_ankle", [option("A", "carbon foot", marks={"R1": "partly"}, costs=["price"]),
                                        option("B", "multiaxial foot")], components, set())
        self.assertEqual(plan.choice_reason, "why")
        # Another option of the same component changing keeps it too.
        plan.set_options("foot_ankle", [option("A", "carbon foot")], components, set())
        self.assertEqual(plan.chosen, {"foot_ankle": "A", "socket": "A"})
        # The chosen option renamed: the configuration and its reason go.
        plan.set_options("socket", [option("A", "PTB")], components, set())
        self.assertEqual((plan.configuration, plan.choice_reason), ({}, None))

    def test_a_requirement_removed_takes_its_marks_and_conflicts(self):
        plan = ProstheticPlan(requirements=[Requirement("R1", "a"), Requirement("R2", "b")],
                              conflicts=[Conflict("R1", "R2", "n")],
                              options={"foot_ankle": [option("A", "x", marks={"R1": "yes", "R2": "no"},
                                                             mark_notes={"R2": "with socks"})]})
        plan.set_requirements([Requirement("R1", "a")], linkable(tt_case()))
        self.assertEqual(plan.options["foot_ankle"][0].marks, {"R1": Mark.YES})
        self.assertEqual((plan.options["foot_ankle"][0].mark_notes, plan.conflicts), ({}, []))
        with self.assertRaises(PlanError):
            plan.set_requirements([Requirement("R1", "a", ["not.a.finding"])], linkable(tt_case()))

    def test_alignment_and_check_socket_versions_are_kept(self):
        plan = ProstheticPlan()
        with self.assertRaises(PlanError):
            plan.save_alignment({"Foot position": " "}, None)  # nothing to keep
        plan.save_alignment({"Foot position": "bench", "Height": "pelvis level"}, None)
        with self.assertRaises(PlanError):
            plan.save_alignment({"Foot position": "bench", "Height": "pelvis level"}, "same")  # no change
        plan.save_alignment({"Foot position": "5 mm posterior", "Height": "pelvis level"}, "knee too straight")
        self.assertEqual([v.number for v in plan.alignment_versions], [1, 2])
        self.assertEqual(plan.alignment_versions[0].values["Foot position"], "bench")  # never changed
        self.assertEqual(plan.alignment.values["Foot position"], "5 mm posterior")
        plan.add_socket_version("redness", "relief")
        plan.add_socket_version("redness fades", None)
        self.assertEqual([(v.number, v.changed) for v in plan.socket_versions], [(1, "relief"), (2, None)])
        with self.assertRaises(PlanError):
            plan.add_socket_version(" ", None)

    def test_an_alert_loops_back_only_to_a_prosthetic_module(self):
        with self.assertRaises(PlanError):
            ProstheticPlan(follow_up=FollowUp(alerts=[Alert("x", "options")]))  # an orthotic page
        with self.assertRaises(PlanError):
            Observation("dynamic_alignment", "x", "flight")  # not a gait phase

    def test_findings_and_provisional_requirements(self):
        case = Case(amputation_level="transtibial", side="left", body_weight_kg=81,
                    residual_limb=ResidualLimb(wound_status="healed", volume_stability="unknown"))
        plan = ProstheticPlan(assessment=Assessment(goal_participation="return to teaching"))
        keys = {f.key for f in case_findings(case, plan)}
        self.assertLessEqual({"residual_limb.wound_status", "body_weight_kg", "assessment.goal_participation"}, keys)
        self.assertNotIn("residual_limb.volume_stability", keys)  # recorded as unknown: a gap, not a finding
        missing = {f.key for f in missing_findings(case, plan)}
        self.assertIn("cognitive_status", missing)
        requirement = Requirement("R5", "simple to put on", ["cognitive_status", "body_weight_kg"])
        self.assertEqual(waiting_on(requirement, case, plan), ["cognitive_status"])
        # The other leg and the K-level are a lower-limb case's only.
        arm = Case(amputation_level="transradial", side="left")
        self.assertFalse({"activity.k_level", "contralateral_limb_status"} & linkable(arm))


# ---- The draft hard stops ---------------------------------------------------------


class HardStopTests(unittest.TestCase):
    def check(self, rule, case, plan=None):
        return next(c for c in hard_stops.case_checks(case, plan) if c.rule == rule)

    def test_open_wound_or_infection(self):
        no_infection = ProstheticPlan(assessment=Assessment(infection="no"))
        infected = ProstheticPlan(assessment=Assessment(infection="yes"))
        for case, plan, status, detail in (
                (tt_case(wound_status="open"), no_infection, "stop", "wound_open"),
                (tt_case(wound_status="healed"), infected, "stop", "infection_yes"),
                (tt_case(wound_status="healing"), no_infection, "judge", "wound_healing"),
                (tt_case(wound_status="healed"), no_infection, "clear", "wound_healed_no_infection"),
                (tt_case(wound_status="healed"), None, "not_checked", "infection_not_recorded"),
                (tt_case(wound_status="unknown"), no_infection, "not_checked", "unknown"),
                (tt_case(), no_infection, "not_checked", "not_recorded")):
            with self.subTest(case.residual_limb.wound_status, plan=plan and plan.assessment.infection):
                c = self.check("open_wound", case, plan)
                self.assertEqual((c.status, c.detail), (status, detail))

    def test_changing_volume(self):
        for volume, status in (("fluctuating", "warn"), ("stable", "clear"), ("unknown", "not_checked"),
                               (None, "not_checked")):
            with self.subTest(volume):
                self.assertEqual(self.check("volume_changing", tt_case(volume_stability=volume)).status, status)

    def test_neuropathic_other_foot(self):
        for neuropathy, team, status, detail in (("yes", "yes", "clear", "team_care"), ("yes", "no", "stop", "team_refer"),
                                                 ("yes", None, "warn", "team_unknown"),
                                                 ("no", None, "clear", "neuropathy_no"),
                                                 (None, None, "not_checked", "not_recorded")):
            with self.subTest(neuropathy=neuropathy, team=team):
                plan = ProstheticPlan(assessment=Assessment(other_foot_neuropathy=neuropathy, diabetic_foot_team=team))
                c = self.check("neuropathic_foot", tt_case(), plan)
                self.assertEqual((c.status, c.detail), (status, detail))
        arm = Case(amputation_level="transradial", side="left")
        self.assertNotIn("neuropathic_foot", [c.rule for c in hard_stops.case_checks(arm)])  # no other foot to check

    def test_every_check_shows_its_rule_as_a_draft_from_the_owners_file(self):
        for c in hard_stops.case_checks(tt_case(), ProstheticPlan()):
            with self.subTest(c.rule):
                self.assertEqual((c.clinic_rule.rule_id, c.clinic_rule.domain), (c.rule, "prosthetics"))
                self.assertFalse(c.clinic_rule.approved)


# ---- The pages ----------------------------------------------------------------------


class ModulePageTests(ProstheticRouteTestCase):
    """A transtibial case with every intake input filled in (prosthetics/tests/helpers.py FULL_FORM)."""

    form = FULL_FORM

    def setUp(self):
        super().setUp()
        resp = self.client.post("/intake", data=self.form)
        self.assertEqual(resp.status_code, 302)
        self.case_id = store.all()[-1].case.case_id
        self.writer_calls = len(self.writer.calls)

    def url(self, page):
        return f"/prosthetics/{self.case_id}/{page}"

    def page(self, page, lang="en"):
        self.client.set_cookie("lang", lang)
        resp = self.client.get(self.url(page))
        self.assertEqual(resp.status_code, 200, page)
        return visible_text(resp.get_data(as_text=True))

    def post(self, page, lang="en", **data):
        self.client.set_cookie("lang", lang)
        return self.client.post(self.url(page), data=data)

    def plan(self) -> ProstheticPlan:
        return store.get(self.case_id).plan

    def test_every_page_opens_in_english_and_arabic(self):
        for page, en, ar in (("assess", "Amputation case assessment", "تقييم حالة البتر"),
                             ("components", "Functional requirements and component support", "المتطلبات الوظيفية"),
                             ("fitting", "Design and fitting decisions", "قرارات التصميم والتركيب"),
                             ("fabrication-sheet", "Fabrication sheet", "ورقة التصنيع"),
                             ("follow-up", "Follow-up and evaluation", "المتابعة والتقييم")):
            with self.subTest(page):
                text = self.page(page)
                self.assertIn(en, text)
                self.assertIn("Decision support: the prosthetist decides", text)
                self.assertIn(ar, self.page(page, "ar"))
        self.client.set_cookie("lang", "en")
        html = self.client.get(self.url("components")).get_data(as_text=True)
        self.assertIn(f'href="{self.url("components")}" aria-current="page">2–3 Requirements &amp; components', html)

    def test_module_1_shows_the_case_as_measured_and_records_the_rest(self):
        text = self.page("assess")
        self.assertIn("Every value keeps how it was measured", text)
        self.assertIn("Set by the prosthetist", text)  # the K-level recorded at intake
        self.assertIn("Draft rule, awaiting the owner's approval", text)
        resp = self.post("assess", action="assessment", how_1="inspection", infection="no",
                         other_foot_neuropathy="yes", joint_range="knee flexion 130°", mob_rows="3",
                         mob_1_name="Two-minute walk test", mob_1_value="112 m", mob_1_how="no walking aid",
                         goal_participation="return to teaching", home_work_setting="stairs at school")
        self.assertEqual(resp.status_code, 302)
        plan = self.plan()
        self.assertEqual(plan.assessment.measured_how, {"residual_limb.wound_status": "inspection"})
        self.assertIs(plan.assessment.other_foot_neuropathy, YesNoUnknown.YES)
        text = self.page("assess")
        for shown in ("inspection", "knee flexion 130°", "Two-minute walk test", "112 m", "return to teaching"):
            self.assertIn(shown, text)
        # The draft rules read what was recorded: no infection and a healed wound clear; the team isn't recorded.
        self.assertIn("Recorded: the wound is healed, no signs of infection", text)
        self.assertIn("Is the diabetic foot team aware?", text)
        # Kept in the case file.
        saved = json.loads((self.cases_dir / f"{self.case_id}.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["plan"]["assessment"]["joint_range"], "knee flexion 130°")

    def test_a_refused_assessment_comes_back_as_sent(self):
        resp = self.post("assess", "ar", action="assessment", joint_range="full", mob_rows="3", mob_1_name="AMPPRO")
        self.assertEqual(resp.status_code, 400)
        text = visible_text(resp.get_data(as_text=True))
        self.assertIn("يحتاج مقياس التنقل إلى اسم الاختبار ونتيجته.", text)
        self.assertIn('value="AMPPRO"', resp.get_data(as_text=True))
        self.assertIsNone(store.get(self.case_id).plan)  # nothing kept

    def test_requirements_then_options_side_by_side_never_ranked(self):
        self.assertEqual(self.post("components", action="requirements", rows="3", req_1_text="Allow changing walking speed",
                                   req_1_finding="activity.k_level", req_1_priority="must",
                                   req_2_text="Be simple to put on", req_2_finding="cognitive_status").status_code, 302)
        self.assertEqual([r.id for r in self.plan().requirements], ["R1", "R2"])
        resp = self.post("components", action="options", component="foot_ankle",
                         opt_A_name="Multiaxial foot", opt_A_mark_R1="partly", opt_A_weight_limit_kg="100",
                         opt_B_name="Energy-storing carbon foot", opt_B_mark_R1="no", opt_B_costs="Stiffer on slopes\nPrice",
                         opt_B_funding="[payer rule as printed]", opt_B_weight_limit_kg="75")
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.headers["Location"].endswith("#component-foot_ankle"))
        text = self.page("components")
        self.assertLess(text.index("Multiaxial foot"), text.index("Energy-storing carbon foot"))  # the order entered
        self.assertIn("Marked by the prosthetist as not addressing a Must requirement:", text)
        self.assertIn("Maker's limit 100 kg · recorded weight 81 kg", text)
        self.assertIn("The recorded weight is above the maker's limit as entered.", text)  # 81 kg over 75 kg
        self.assertEqual(text.count("The recorded weight is above"), 1)
        for words in ("best option", "recommended", "ranked first", "top choice"):  # no verdict on an option
            self.assertNotIn(words, text.lower())

    def test_the_configuration_and_its_reason_are_logged(self):
        self.post("components", action="options", component="foot_ankle", opt_A_name="Multiaxial foot")
        self.post("components", action="options", component="socket", opt_A_name="TSB, silicone liner, pin lock")
        refused = self.post("configuration", action="configuration", chosen_foot_ankle="A", reason=" ")
        self.assertEqual(refused.status_code, 400)
        self.assertEqual(read_decisions(self.case_id), [])  # nothing logged
        resp = self.post("configuration", action="configuration", chosen_foot_ankle="A", chosen_socket="A",
                         reason="Volume still changing: pin lock with socks")
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.headers["Location"].endswith(f"/prosthetics/{self.case_id}/fitting?chosen=1"))
        [entry] = read_decisions(self.case_id)
        self.assertEqual((entry["log_version"], entry["decision"], entry["domain"]), (LOG_VERSION, "design_choice",
                                                                                       "prosthetics"))
        self.assertEqual(entry["plan"]["configuration"], {"foot_ankle": "A", "socket": "A"})
        self.assertEqual(entry["note"], "Volume still changing: pin lock with socks")
        self.assertIn("The configuration and its reason are in the review log.",
                      visible_text(self.client.get(resp.headers["Location"]).get_data(as_text=True)))
        # Renaming a chosen option takes the configuration with it (the log keeps it as it was made).
        self.post("components", action="options", component="socket", opt_A_name="PTB, foam liner, sleeve")
        self.assertEqual(self.plan().configuration, {})
        self.assertEqual(len(read_decisions(self.case_id)), 1)

    def test_module_4_logs_steps_observations_versions_and_alignment(self):
        self.assertEqual(self.post("fitting", action="steps", step_shape_capture_status="done",
                                   step_shape_capture_notes="3D scan, approved",
                                   step_dynamic_alignment_status="in_progress").status_code, 302)
        self.assertIs(self.plan().step(FittingStep.SHAPE_CAPTURE).status, StepStatus.DONE)
        self.assertEqual(self.post("fitting", action="observations", obs_rows="3", obs_1_step="dynamic_alignment",
                                   obs_1_phase="loading_response", obs_1_seen="knee stays straight",
                                   obs_1_adjustment="foot 5 mm posterior").status_code, 302)
        refused = self.post("fitting", action="observations", obs_rows="3", obs_1_seen="heel first")  # no step
        self.assertEqual(refused.status_code, 400)
        self.post("fitting", action="socket", socket_seen="redness over the fibular head", socket_changed="relief")
        self.post("fitting", action="socket", socket_seen="redness fades within 10 minutes")
        self.post("fitting", action="alignment", align_rows="3", align_1_name="Foot position", align_1_value="bench")
        self.post("fitting", action="alignment", align_rows="3", align_1_name="Foot position",
                  align_1_value="5 mm posterior", align_note="knee too straight")
        same = self.post("fitting", action="alignment", align_rows="3", align_1_name="Foot position",
                         align_1_value="5 mm posterior")
        self.assertEqual(same.status_code, 400)
        plan = self.plan()
        self.assertEqual([v.number for v in plan.socket_versions], [1, 2])
        self.assertEqual([v.values["Foot position"] for v in plan.alignment_versions], ["bench", "5 mm posterior"])
        text = self.page("fitting")
        for shown in ("3D scan, approved", "Loading response", "knee stays straight", "foot 5 mm posterior",
                      "redness fades within 10 minutes", "Version 2", "Every version (2)",
                      "The clinic's own checklist is not set yet"):
            self.assertIn(shown, text)
        sheet = self.page("fabrication-sheet")
        self.assertIn("5 mm posterior", sheet)
        self.assertIn("Test case · fake data", sheet)

    def test_module_5_follow_up_loops_back_to_the_modules(self):
        self.post("follow-up", action="measures", measure_rows="3", measure_1_name="Sock ply", due_next="questionnaire")
        self.post("follow-up", action="visits", visit_rows="3", visit_1_name="2-week check", visit_1_status="done",
                  visit_1_value_1="3", visit_2_name="6-week review", visit_2_status="due", visit_2_date="2026-11-03")
        resp = self.post("follow-up", action="alerts", alert_rows="1", alert_1_text="Sock ply rising",
                         alert_1_back_to="fitting")
        self.assertEqual(resp.status_code, 302)
        refused = self.post("follow-up", action="alerts", alert_rows="1", alert_1_text="x", alert_1_back_to="options")
        self.assertEqual(refused.status_code, 400)  # an orthotic page
        html = self.client.get(self.url("follow-up")).get_data(as_text=True)
        self.assertIn(f'href="{self.url("fitting")}"', html)
        text = visible_text(html)
        for shown in ("Sock ply rising", "Refit in design and fitting →", "6-week review due 2026-11-03.",
                      "Refit the socket", "Review the components", "Re-assess"):
            self.assertIn(shown, text)

    def test_the_review_page_and_the_map_lead_to_the_modules(self):
        html = self.client.get(f"/review/{self.case_id}").get_data(as_text=True)
        for page in ("assess", "components", "fitting", "follow-up"):
            self.assertIn(f'href="{self.url(page)}"', html)
        self.assertIn("← Module 1: the assessment", visible_text(html))
        self.assertIn(f'href="{self.url("assess")}"', self.client.get("/prosthetics").get_data(as_text=True))

    def test_module_pages_send_nothing_to_the_ai(self):
        self.post("assess", action="assessment", joint_range="full")
        self.post("components", action="requirements", rows="1", req_1_text="x")
        for page in ("assess", "components", "fitting", "follow-up"):
            self.page(page)
        self.assertEqual(len(self.writer.calls), self.writer_calls)

    def test_another_domains_case_is_not_found_here(self):
        self.client.post("/intake/orthotics", data={"condition": "stroke", "side": "left"})
        orthotic = store.all()[-1].case.case_id
        self.assertEqual(self.client.get(f"/prosthetics/{orthotic}/assess").status_code, 404)
        self.assertEqual(self.client.get(f"/orthotics/{self.case_id}/analysis").status_code, 404)

    def test_a_case_saved_before_its_plan_still_opens(self):
        record = store.get(self.case_id)
        data = record_to_dict(record)
        self.assertIsNone(data["plan"])
        self.assertIsNone(record_from_dict(data).plan)
        self.assertIn("No configuration recorded yet.", self.page("fitting"))


class TransfemoralSourcesTests(ProstheticRouteTestCase):
    """A transfemoral case: the knee has a statement from the sources (the fake search's knee passage)."""

    def test_an_option_links_the_sources_shown_for_its_component(self):
        self.client.post("/intake", data={"amputation_level": "transfemoral", "side": "left", "k_level": "K3"})
        record = store.all()[-1]
        knee = [c.statement.id for s in record.components.sections if s.component == "knee" for c in s.statements]
        self.assertTrue(knee)
        url = f"/prosthetics/{record.case.case_id}/components"
        refused = self.client.post(url, data={"action": "options", "component": "knee", "opt_A_name": "MPK",
                                              "opt_A_source": "not-shown"})
        self.assertEqual(refused.status_code, 400)
        self.client.post(url, data={"action": "options", "component": "knee", "opt_A_name": "Microprocessor knee",
                                    "opt_A_source": knee[0]})
        text = visible_text(self.client.get(url).get_data(as_text=True))
        self.assertIn("Sources linked", text)
        self.assertIn("Source grade:", text)
        self.assertIn("What the sources say about this component", text)


if __name__ == "__main__":
    unittest.main()
