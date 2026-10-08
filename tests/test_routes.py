"""Tests for the intake and review pages, through Flask's test client."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from intake.routes import _optional_list
from knowledge.models import ProtocolChunk
from knowledge.retrieval import KnowledgeBaseMissing
from review.decision_log import read_decisions
from shared.store import store

BASE_FORM = {"amputation_level": "transtibial", "side": "left"}

# Every input on the intake form filled in.
FULL_FORM = {
    **BASE_FORM,
    "etiology": "vascular", "months_since_amputation": "5",
    "age_years": "64", "body_weight_kg": "81",
    "wound_status": "healed", "volume_stability": "stable", "skin_condition": "intact",
    "length_description": "mid-length", "pain": "mild phantom pain", "sensation": "reduced",
    "k_level": "K2", "activity_description": "walks indoors", "functional_goals": "walk to the shop",
    "device_1_description": "PTB socket, SACH foot", "device_1_years": "2",
    "device_1_current": "no", "device_1_issues": "loose fit",
    "comorbidities": "Diabetes", "contralateral_limb_status": "foot ulcer healed",
    "cognitive_status": "intact", "intake_notes": "test case",
}

VOLUME_PASSAGE = ProtocolChunk(
    chunk_id="test_guideline_2024-0007",
    text="Residual limb volume should be stable before the definitive socket is cast.",
    source="01_guidelines/test.pdf",
    title="Test Guideline",
    year=2024,
    page=14,
    end_page=14,
    language="en",
    score=0.71,
)


def fake_retrieval(case):
    """Stands in for the real search, so tests never load the 2.3 GB model."""
    return {"residual_limb.volume_stability": [VOLUME_PASSAGE]}


class OptionalListTests(unittest.TestCase):
    def test_blank_is_not_recorded(self):
        for raw in (None, "", "  \r\n  \n"):
            self.assertIsNone(_optional_list(raw))

    def test_none_means_asked_none_reported(self):
        self.assertEqual(_optional_list("none"), [])
        self.assertEqual(_optional_list("\n None \n"), [])

    def test_one_item_per_line(self):
        self.assertEqual(
            _optional_list("Diabetes\r\n\r\n  Hypertension  \r\n"),
            ["Diabetes", "Hypertension"],
        )


class RouteTestCase(unittest.TestCase):
    def setUp(self):
        app = create_app()
        app.testing = True
        self.client = app.test_client()
        retrieval = patch("intake.routes.retrieve_relevant_chunks", side_effect=fake_retrieval)
        retrieval.start()
        self.addCleanup(retrieval.stop)
        # Decisions go to a temporary log, never to the real data/review_log.jsonl.
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.log_path = Path(tmp.name) / "review_log.jsonl"
        log_path = patch("review.decision_log.REVIEW_LOG_PATH", self.log_path)
        log_path.start()
        self.addCleanup(log_path.stop)

    def post_intake(self, **fields):
        return self.client.post("/intake", data={**BASE_FORM, **fields})


class IntakeRouteTests(RouteTestCase):
    def test_form_renders(self):
        resp = self.client.get("/intake")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'name="comorbidities"', resp.data)
        self.assertIn(b'name="no_prior_devices"', resp.data)
        self.assertIn(b'name="device_3_issues"', resp.data)
        self.assertNotIn(b'class="error"', resp.data)

    def test_fully_filled_form_has_no_gaps(self):
        resp = self.client.post("/intake", data=FULL_FORM)
        self.assertEqual(store.all()[-1].gaps, [])
        page = self.client.get(resp.headers["Location"]).get_data(as_text=True)
        self.assertIn("No gaps identified", page)
        self.assertIn("PTB socket, SACH foot · 2.0 years · no longer used · issues: loose fit", page)

    def test_prior_devices_from_rows(self):
        self.post_intake(
            device_1_description="  PTB socket  ", device_1_years="2.5", device_1_current="no",
            device_3_description="pin-lock liner", device_3_current="yes",  # row 2 left empty
        )
        devices = store.all()[-1].case.prior_devices
        self.assertEqual([d.device_description for d in devices], ["PTB socket", "pin-lock liner"])
        self.assertEqual((devices[0].years_used, devices[0].currently_using, devices[0].issues),
                         (2.5, False, None))
        self.assertIs(devices[1].currently_using, True)

    def test_no_prior_prosthesis_is_not_a_gap(self):
        self.post_intake(no_prior_devices="1")
        record = store.all()[-1]
        self.assertEqual(record.case.prior_devices, [])
        self.assertNotIn("prior_devices", [g.field for g in record.gaps])

    def test_blank_prior_devices_not_recorded(self):
        self.post_intake()
        record = store.all()[-1]
        self.assertIsNone(record.case.prior_devices)
        self.assertIn("prior_devices", [g.field for g in record.gaps])

    def test_bad_prior_devices_rejected(self):
        for fields, message in [
            ({"device_2_years": "3"}, b"prior device 2: describe the device"),
            ({"no_prior_devices": "1", "device_1_description": "socket"}, b"is ticked, but a device"),
            ({"device_1_description": "socket", "device_1_years": "-1"}, b"prior device 1: years_used"),
            ({"device_1_description": "socket", "device_1_current": "maybe"}, b"expected yes or no"),
        ]:
            with self.subTest(**fields):
                before = len(store.all())
                resp = self.post_intake(**fields)
                self.assertEqual(resp.status_code, 400)
                self.assertIn(message, resp.data)
                self.assertEqual(len(store.all()), before)

    def test_valid_submission_saves_and_redirects_to_review(self):
        resp = self.post_intake(
            age_years="58", wound_status="healed", comorbidities="Diabetes\nHypertension"
        )
        self.assertEqual(resp.status_code, 302)
        case = store.all()[-1].case
        self.assertEqual(case.age_years, 58)
        self.assertEqual(case.residual_limb.wound_status.value, "healed")
        self.assertEqual(case.comorbidities, ["Diabetes", "Hypertension"])
        self.assertEqual(self.client.get(resp.headers["Location"]).status_code, 200)

    def test_blank_comorbidities_not_recorded(self):
        self.post_intake(comorbidities="")
        self.assertIsNone(store.all()[-1].case.comorbidities)

    def test_bad_values_rejected_with_message(self):
        for fields in [
            {"age_years": "-5"},
            {"body_weight_kg": "0"},
            {"age_years": "abc"},
            {"amputation_level": "banana"},
            {"wound_status": "bleeding"},
        ]:
            with self.subTest(**fields):
                before = len(store.all())
                resp = self.post_intake(**fields)
                self.assertEqual(resp.status_code, 400)
                self.assertIn(b"Case not saved:", resp.data)
                self.assertEqual(len(store.all()), before)

    def test_missing_required_field(self):
        for data, name in [({"side": "left"}, b"amputation_level is required"),
                           ({"amputation_level": "transtibial"}, b"side is required"),
                           ({"amputation_level": "transtibial", "side": ""}, b"side is required")]:
            with self.subTest(**data):
                resp = self.client.post("/intake", data=data)
                self.assertEqual(resp.status_code, 400)
                self.assertIn(name, resp.data)  # the form with a message, not a crash page


class ReviewRouteTests(RouteTestCase):
    def test_unknown_case_is_404(self):
        self.assertEqual(self.client.get("/review/does-not-exist").status_code, 404)

    def test_gaps_show_the_quoted_source(self):
        page = self.client.get(self.post_intake().headers["Location"]).get_data(as_text=True)
        self.assertIn("Residual limb volume stability", page)
        self.assertIn("Residual limb volume should be stable before the definitive socket is cast.", page)
        self.assertIn("Test Guideline (2024), p. 14", page)
        self.assertIn("test_guideline_2024-0007", page)
        self.assertIn("The list may be incomplete", page)
        self.assertIn("No source cited.", page)  # the other gaps have no passage here

    def test_missing_source_library_is_shown(self):
        with patch("intake.routes.retrieve_relevant_chunks",
                   side_effect=KnowledgeBaseMissing("No vector store.")):
            resp = self.post_intake()
        page = self.client.get(resp.headers["Location"]).get_data(as_text=True)
        self.assertIn("The source library was not searched: No vector store.", page)
        self.assertIn("Residual limb wound status", page)  # gaps are still listed

    def new_case_id(self) -> str:
        self.post_intake()
        return store.all()[-1].case.case_id

    def post_decision(self, case_id: str, **data):
        return self.client.post(f"/review/{case_id}/decision", data=data, follow_redirects=True)

    def test_gaps_offer_a_judgement(self):
        page = self.client.get(self.post_intake().headers["Location"]).get_data(as_text=True)
        self.assertIn('name="gap:residual_limb.volume_stability" value="needed"', page)
        self.assertIn('name="gap:residual_limb.volume_stability" value="not_needed"', page)

    def test_decision_is_saved_to_the_log_and_shown(self):
        case_id = self.new_case_id()
        resp = self.post_decision(
            case_id,
            decision="approve",
            note="looks complete",
            **{"gap:residual_limb.volume_stability": "needed", "gap:residual_limb.wound_status": ""},
        )
        self.assertEqual(resp.status_code, 200)
        page = resp.get_data(as_text=True)
        self.assertIn("Decision saved to the review log: <strong>approve</strong>", page)
        self.assertIn("Logged decisions for this case (1)", page)
        self.assertIn("looks complete", page)

        [entry] = read_decisions(case_id, path=self.log_path)
        self.assertEqual((entry["decision"], entry["note"]), ("approve", "looks complete"))
        judgements = {g["field"]: g["reviewer_judgement"] for g in entry["gaps"]}
        self.assertEqual(judgements["residual_limb.volume_stability"], "needed")
        self.assertIsNone(judgements["residual_limb.wound_status"])  # left on "not marked"
        volume = next(g for g in entry["gaps"] if g["field"] == "residual_limb.volume_stability")
        self.assertEqual(volume["source"]["citation"], "Test Guideline (2024), p. 14")

    def test_each_decision_is_added(self):
        case_id = self.new_case_id()
        self.post_decision(case_id, decision="reject", note="duplicate")
        page = self.post_decision(case_id, decision="approve").get_data(as_text=True)
        self.assertIn("Logged decisions for this case (2)", page)
        self.assertEqual([e["decision"] for e in read_decisions(case_id, path=self.log_path)],
                         ["reject", "approve"])

    def test_invalid_decision_refused_and_not_logged(self):
        case_id = self.new_case_id()
        for data in [{"decision": "maybe"}, {},
                     {"decision": "approve", "gap:residual_limb.wound_status": "yes"}]:
            with self.subTest(**data):
                resp = self.post_decision(case_id, **data)
                self.assertEqual(resp.status_code, 400)
                self.assertIn(b"Decision not saved:", resp.data)
        self.assertEqual(read_decisions(path=self.log_path), [])

    def test_edit_without_note_keeps_the_choices(self):
        case_id = self.new_case_id()
        resp = self.post_decision(
            case_id, decision="edit", **{"gap:residual_limb.volume_stability": "not_needed"}
        )
        self.assertEqual(resp.status_code, 400)
        page = resp.get_data(as_text=True)
        self.assertIn("An edit needs a note", page)
        self.assertIn('value="not_needed" checked', page)
        self.assertEqual(read_decisions(path=self.log_path), [])

    def test_decision_for_unknown_case_is_404(self):
        self.assertEqual(self.post_decision("does-not-exist", decision="approve").status_code, 404)


if __name__ == "__main__":
    unittest.main()
