"""Tests for the intake and review pages, through Flask's test client."""

import unittest
from unittest.mock import patch

from app import create_app
from intake.routes import _optional_list
from knowledge.models import ProtocolChunk
from knowledge.retrieval import KnowledgeBaseMissing
from shared.store import store

BASE_FORM = {"amputation_level": "transtibial", "side": "left"}

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

    def post_intake(self, **fields):
        return self.client.post("/intake", data={**BASE_FORM, **fields})


class IntakeRouteTests(RouteTestCase):
    def test_form_renders(self):
        resp = self.client.get("/intake")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'name="comorbidities"', resp.data)
        self.assertNotIn(b'class="error"', resp.data)

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
        resp = self.client.post("/intake", data={"side": "left"})
        self.assertEqual(resp.status_code, 400)


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

    @patch("review.routes.record_decision")
    def test_decision_is_recorded_and_confirmed(self, record_decision):
        case_url = self.post_intake().headers["Location"]
        case_id = store.all()[-1].case.case_id

        resp = self.client.post(
            f"/review/{case_id}/decision",
            data={"decision": "approve", "note": "looks complete"},
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Decision recorded", resp.data)
        record_decision.assert_called_once_with(
            case_id=case_id, decision="approve", note="looks complete"
        )
        self.assertTrue(case_url.endswith(case_id))


if __name__ == "__main__":
    unittest.main()
