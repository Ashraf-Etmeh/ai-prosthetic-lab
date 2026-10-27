"""Tests for rehabilitation (rehabilitation/; plan Part 9, SYSTEM_DESIGN.md §6.4).

The search is replaced (no embedding model), and cases, logs and people go to temporary folders
(shared/testing.py RouteTestCase).
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from knowledge.retrieval import KnowledgeBaseMissing
from knowledge.tests.test_retrieval import make_store
from orthotics.plan import OrthoticPlan
from orthotics.tests.test_orthotics import full_case
from prosthetics.case import Case
from prosthetics.tests.helpers import KNEE_PASSAGE, ProstheticRouteTestCase
from rehabilitation import sources
from rehabilitation.plan import (
    Goal,
    GoalScore,
    Intervention,
    InterventionKind,
    Observation,
    PlanError,
    RehabPlan,
    TeamRole,
    next_id,
)
from record.timeline import record_view
from record import people
from shared.dates import DateError
from shared.requirements import Requirement
from shared.store import CaseRecord, CaseStore, store
from shared.testing import chunk_record, fake_embed, visible_text


def full_plan() -> RehabPlan:
    return RehabPlan(
        agreed_on="2026-07-06", review_every="4 weeks",
        goals=[Goal("G1", "participation", "Visit family across town by bus", "12 weeks"),
               Goal("G2", "activity", "Walk 400 m outdoors", None, "2026-11-01")],
        scores=[GoalScore("G2", -1, "2026-09-01"), GoalScore("G2", 0, "2026-10-13", "reached")],
        interventions=[Intervention("I1", "gait_training", None, ["G1", "G2"], "30 min every session"),
                       Intervention("I2", "other", "Bus practice", ["G1"])],
        phases={"outpatient": {"status": "current", "when": "weeks 1-12"}},
        team=[{"role": "physiotherapist", "does": "plan owner"}],
        observations=[Observation("Knee extends fast on stairs", "orthotist", "2026-10-14T10:00:00+00:00")],
    )


class PlanTests(unittest.TestCase):
    def test_round_trip(self):
        plan = full_plan()
        again = RehabPlan.from_dict(json.loads(json.dumps(plan.to_dict())))
        self.assertEqual(again.to_dict(), plan.to_dict())
        self.assertEqual(RehabPlan.from_dict({}).to_dict(), RehabPlan().to_dict())
        self.assertTrue(RehabPlan().empty)

    def test_what_the_plan_refuses(self):
        for change in ({"goals": [Goal("G1", "activity", "a"), Goal("G1", "activity", "b")]},
                       {"interventions": [Intervention("I1", "gait_training", None, ["G9"])]},
                       {"interventions": [Intervention("I1", "other")]}):
            with self.subTest(change):
                with self.assertRaises(PlanError):
                    RehabPlan(**{**full_plan().__dict__, **change})
        with self.assertRaises(PlanError):
            GoalScore("G1", 3, "2026-10-13")
        with self.assertRaises(DateError):
            GoalScore("G1", 1, "13/10/2026")

    def test_reading_it(self):
        plan = full_plan()
        self.assertEqual(plan.latest_score("G2").score, 0)
        self.assertIsNone(plan.latest_score("G1"))
        self.assertEqual(len(plan.open_observations()), 1)
        self.assertEqual(next_id("G", plan.goal_ids()), "G3")
        self.assertEqual(next_id("T", []), "T1")

    def test_kept_with_the_case_and_older_files_read(self):
        with tempfile.TemporaryDirectory() as folder:
            case_store = CaseStore(Path(folder))
            record = CaseRecord(case=Case(amputation_level="transtibial", side="left"), rehab=full_plan())
            case_store.save(record)
            path = Path(folder) / f"{record.case.case_id}.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["case_file_version"], 5)
            self.assertEqual(CaseStore(Path(folder)).get(record.case.case_id).rehab.to_dict(), full_plan().to_dict())
            data.pop("rehab")  # a version 4 file
            data["case_file_version"] = 4
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertIsNone(CaseStore(Path(folder)).get(record.case.case_id).rehab)


class SourcesTests(unittest.TestCase):
    def setUp(self):
        sources._cache.clear()
        self.addCleanup(sources._cache.clear)

    def store(self):
        return make_store(
            chunk_record("vadod_stroke-0001", "Gait training with an orthosis improves walking", domains=("rehabilitation",)),
            chunk_record("vadod_stroke-0002", "Gait training again in the same guideline", domains=("rehabilitation",)),
            chunk_record("who_package-0001", "Walking training for people after stroke", domains=("rehabilitation",)),
            chunk_record("ul_only-0001", "Gait training for an arm amputation", domains=("rehabilitation",),
                         limbs=("upper",)),
            chunk_record("device_only-0001", "Gait training in an orthotics manual", domains=("orthotics",)),
        )

    def test_passages_for_each_kind_never_the_therapists_own(self):
        found = sources.find_passages([InterventionKind.GAIT_TRAINING, InterventionKind.OTHER,
                                       InterventionKind.MIRROR_THERAPY], "lower", store=self.store(),
                                      embed=fake_embed)
        self.assertNotIn("other", found)  # never searched
        self.assertEqual(found["mirror_therapy"], [])  # nothing mentions it: the page says so
        ids = [c.chunk_id for c in found["gait_training"]]
        self.assertLessEqual(len(ids), sources.PASSAGES_PER_ITEM)
        self.assertLessEqual(sum(1 for i in ids if i.startswith("vadod_stroke")), sources.PER_DOCUMENT)
        self.assertNotIn("ul_only-0001", ids)  # the other limb
        self.assertNotIn("device_only-0001", ids)  # not a rehabilitation source
        self.assertEqual(sources.find_passages([InterventionKind.OTHER], "lower", store=self.store()), {})

    def test_every_kind_but_the_therapists_own_has_its_search(self):
        self.assertEqual(set(sources.INTERVENTIONS), set(InterventionKind) - {InterventionKind.OTHER})


def fake_find(kinds, limb):
    return {k.value: [KNEE_PASSAGE] for k in kinds if k is InterventionKind.GAIT_TRAINING}


class RehabRouteTests(ProstheticRouteTestCase):
    def setUp(self):
        super().setUp()
        search = patch("rehabilitation.routes.find_passages", side_effect=fake_find)
        search.start()
        self.addCleanup(search.stop)
        self.case_id = self.post_intake().headers["Location"].split("/review/")[1]
        self.base = f"/rehabilitation/{self.case_id}"

    def post(self, page: str, **data):
        return self.client.post(f"{self.base}/{page}", data=data)

    def set_goals(self):
        self.assertEqual(self.post("plan", action="goals", goal_rows="2", goal_1_level="participation",
                                   goal_1_text="Visit family across town", goal_2_level="activity",
                                   goal_2_text="Walk 400 m outdoors").status_code, 302)

    def test_first_page_and_tabs(self):
        page = self.client.get("/rehabilitation").get_data(as_text=True)
        self.assertIn(self.case_id, page)
        self.assertIn(f'href="{self.base}/plan"', page)
        self.assertIn('title="Open a case first (Rehabilitation)"', page)  # no case open: the tabs say so
        plan_page = self.client.get(f"{self.base}/plan").get_data(as_text=True)
        self.assertIn(f'href="{self.base}/progress"', plan_page)  # the tabs keep the case
        self.assertIn("Decision support: the therapist decides", visible_text(plan_page))
        self.assertEqual(self.client.get("/rehabilitation/nope/plan").status_code, 404)

    def test_goals_and_interventions_with_their_sources(self):
        self.set_goals()
        resp = self.post("plan", action="interventions", int_rows="2", int_1_kind="gait_training",
                         int_1_goal=["G1", "G2"], int_1_dose="30 min", int_2_kind="other", int_2_name="Bus practice")
        self.assertEqual(resp.status_code, 302)
        plan = store.get(self.case_id).rehab
        self.assertEqual([(i.id, i.kind.value, i.goals) for i in plan.interventions],
                         [("I1", "gait_training", ["G1", "G2"]), ("I2", "other", [])])
        page = visible_text(self.client.get(f"{self.base}/plan").get_data(as_text=True))
        self.assertIn("For prosthetic ambulators, we suggest", page)  # quoted as printed
        self.assertIn("No source in the library: the therapist's own.", page)
        self.assertNotIn("recommend", page.lower())

    def test_refusals_change_nothing(self):
        self.set_goals()
        for data, words in (
            ({"action": "goals", "goal_rows": "1", "goal_1_text": "No level"}, "Choose each goal's ICF level."),
            ({"action": "interventions", "int_rows": "1", "int_1_kind": "other"}, "Name the therapist's own"),
            ({"action": "interventions", "int_rows": "1", "int_1_kind": "gait_training", "int_1_goal": "G9"},
             "A value could not be read."),
        ):
            with self.subTest(data):
                resp = self.post("plan", **data)
                self.assertEqual(resp.status_code, 400)
                self.assertIn(words, visible_text(resp.get_data(as_text=True)))
        self.assertEqual(store.get(self.case_id).rehab.goal_ids(), ["G1", "G2"])

    def test_removing_a_goal_leaves_what_named_it(self):
        self.set_goals()
        self.post("plan", action="interventions", int_rows="1", int_1_kind="balance_training", int_1_goal=["G1", "G2"])
        self.post("plan", action="goals", goal_rows="2", goal_1_id="G1", goal_1_level="participation",
                  goal_1_text="Visit family across town", goal_2_id="G2", goal_2_text="")
        self.assertEqual(store.get(self.case_id).rehab.interventions[0].goals, ["G1"])

    def test_progress_measures_and_scores(self):
        self.set_goals()
        self.post("progress", action="measures", measure_rows="1", measure_1_name="Six-minute walk", measure_1_unit="m")
        self.post("progress", action="visits", visit_rows="1", visit_1_name="Week 0", visit_1_date="2026-09-01",
                  visit_1_status="done", visit_1_value_1="180")
        self.assertEqual(self.post("progress", action="score", goal="G2", score="−1", on="2026-09-01").status_code, 302)
        self.assertEqual(self.post("progress", action="score", goal="G2", score="3", on="2026-09-01").status_code, 400)
        self.assertEqual(self.post("progress", action="score", goal="G2", score="1", on="").status_code, 400)
        plan = store.get(self.case_id).rehab
        self.assertEqual([(s.goal, s.score) for s in plan.scores], [("G2", -1)])
        page = visible_text(self.client.get(f"{self.base}/progress").get_data(as_text=True))
        self.assertIn("180", page)
        self.assertIn("not set yet", page)  # the smallest change that matters is the owner's
        self.assertIn("−1", page)

    def test_training_tied_to_the_device_requirements(self):
        record = CaseRecord(case=full_case(), plan=OrthoticPlan(requirements=[Requirement("R2", "heel first")]))
        store.save(record)
        base = f"/rehabilitation/{record.case.case_id}/training"
        resp = self.client.post(base, data={"action": "tasks", "task_rows": "1", "task_1_text": "Heel-first stepping",
                                            "task_1_trains": "R2", "task_1_status": "with_cues"})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.client.post(base, data={"action": "tasks", "task_rows": "1", "task_1_text": "x",
                                                      "task_1_trains": "R9"}).status_code, 400)
        self.client.post(base, data={"action": "observation", "text": "Knee extends fast on stairs",
                                     "for_role": "orthotist"})
        page = self.client.get(base).get_data(as_text=True)
        self.assertIn('value="orthotist" selected', page)  # the domain's own specialist, from its nav.py
        follow_up = visible_text(self.client.get(f"/orthotics/{record.case.case_id}/follow-up").get_data(as_text=True))
        self.assertIn("Knee extends fast on stairs", follow_up)  # on the orthotist's own page
        self.client.post(base, data={"action": "answer", "n": "1", "answer": "Stiffer joint at the next visit"})
        self.assertEqual(store.get(record.case.case_id).rehab.open_observations(), [])
        self.assertEqual(self.client.post(base, data={"action": "answer", "n": "1", "answer": "again"}).status_code, 400)

    def test_home_programme_flagged_until_checked(self):
        self.post("training", action="home", home_ar="المشي في الممر", home_en="Walk in the hall")
        sheet = self.client.get(f"{self.base}/home-programme?lang=ar").get_data(as_text=True)
        self.assertIn("المشي في الممر", sheet)
        self.assertIn("has not been checked by an Arabic-reading therapist", sheet)
        self.post("training", action="home", home_ar="المشي في الممر", home_en="Walk in the hall",
                  home_checked_by="Arabic-reading physiotherapist")
        self.assertNotIn("has not been checked", self.client.get(f"{self.base}/home-programme?lang=ar")
                         .get_data(as_text=True))

    def test_team_record_handover_signed_and_final(self):
        self.post("team", action="entry", on="2026-10-20", role="physiotherapist", kind="therapy",
                  text="Outdoor walking started")
        self.assertEqual(self.post("team", action="entry", on="2026-10-20", role="physiotherapist",
                                   text="no kind").status_code, 400)
        self.assertEqual(self.post("team", action="sign", signed_by="physiotherapist").status_code, 400)  # none yet
        self.post("team", action="handover", text="Walking 220 m.", written_by="physiotherapist")
        self.post("team", action="sign", signed_by="physiotherapist")
        self.assertEqual(self.post("team", action="sign", signed_by="physiotherapist").status_code, 400)  # final
        self.post("team", action="handover", text="Walking 260 m.", written_by="occupational_therapist")
        plan = store.get(self.case_id).rehab
        self.assertEqual([(h.number, bool(h.signed_at)) for h in plan.handovers], [(1, True), (2, False)])
        page = visible_text(self.client.get(f"{self.base}/team?kind=therapy").get_data(as_text=True))
        self.assertIn("Outdoor walking started", page)
        self.assertIn("Decision support: the team decides", page)
        self.assertNotIn("Outdoor walking started",
                         visible_text(self.client.get(f"{self.base}/team?kind=medical").get_data(as_text=True)))

    def test_library_missing_and_arabic_pages(self):
        self.set_goals()
        self.post("plan", action="interventions", int_rows="1", int_1_kind="gait_training")
        with patch("rehabilitation.routes.find_passages", side_effect=KnowledgeBaseMissing("No vector store.")):
            page = visible_text(self.client.get(f"{self.base}/plan").get_data(as_text=True))
        self.assertIn("No vector store.", page)
        self.client.set_cookie("lang", "ar")
        for module in ("plan", "progress", "training", "team"):
            with self.subTest(module):
                self.assertEqual(self.client.get(f"{self.base}/{module}").status_code, 200)
        self.assertIn("خطة التأهيل", self.client.get(f"{self.base}/plan").get_data(as_text=True))
        self.client.delete_cookie("lang")

    def test_the_patient_record_shows_rehabilitation(self):
        resp = self.client.post("/record/new")
        code = resp.headers["Location"].split("/record/")[1].split("/")[0]
        self.client.post(f"/record/{code}/consent", data={"item": "care_record", "answer": "agreed",
                                                          "consent_lang": "en"})
        case_id = self.post_intake(person_code=code).headers["Location"].split("/review/")[1]
        base = f"/rehabilitation/{case_id}"
        self.client.post(f"{base}/plan", data={"action": "agreed", "agreed_on": "2026-07-06"})
        self.client.post(f"{base}/team", data={"action": "entry", "on": "2026-10-20", "role": "orthotist",
                                               "kind": "device", "text": "Strap replaced"})
        kinds = {e.kind for e in record_view(people.get_person(code)).events}
        self.assertLessEqual({"rehab_plan", "team_entry"}, kinds)
        page = visible_text(self.client.get(f"/record/{code}").get_data(as_text=True))
        self.assertIn("Rehabilitation goals agreed", page)
        self.assertIn("Strap replaced", page)


if __name__ == "__main__":
    unittest.main()
