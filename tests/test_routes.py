"""Tests for the intake and review pages, through Flask's test client."""

import unittest
from unittest.mock import patch

from app import create_app
from intake.routes import _optional_list
from shared.store import store

BASE_FORM = {"amputation_level": "transtibial", "side": "left"}


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
