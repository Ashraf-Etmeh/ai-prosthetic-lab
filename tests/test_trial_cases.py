"""Tests for the prepared trial cases (data/trial/cases/) and intake/load_trial_cases.py."""

import json
import re
import tempfile
import unittest
from dataclasses import asdict, fields
from pathlib import Path
from unittest.mock import patch

from app import create_app
from intake.load_trial_cases import TRIAL_CASES_DIR, load, read_case
from intake.routes import analyse_case
from shared.case_schema import ActivityProfile, AmputationLevel, Case, PriorDevice, ResidualLimb
from shared.store import store
from tests.test_routes import fake_retrieval

FILES = sorted(TRIAL_CASES_DIR.glob("*.json"))
CASE_FIELDS = {f.name for f in fields(Case)}


def nested_fields(cls) -> set[str]:
    return {f.name for f in fields(cls)}


class TrialCaseFileTests(unittest.TestCase):
    def test_ten_to_fifteen_cases(self):
        self.assertTrue(10 <= len(FILES) <= 15, len(FILES))

    def test_each_file_is_a_valid_case_named_by_its_id(self):
        for path in FILES:
            with self.subTest(path.name):
                case = read_case(path)
                self.assertRegex(case.case_id, r"^trial-\d\d$")
                self.assertEqual(Case.from_dict(case.to_dict()).to_dict(), case.to_dict())

    def test_only_case_fields_so_no_identifiers(self):
        # Case has no field for a name, birth date, address or record number,
        # so a file using only Case fields can't hold one in a field of its own.
        for path in FILES:
            data = json.loads(path.read_text(encoding="utf-8"))
            with self.subTest(path.name):
                self.assertLessEqual(set(data), CASE_FIELDS - {"created_at"})
                self.assertLessEqual(set(data.get("residual_limb", {})), nested_fields(ResidualLimb))
                self.assertLessEqual(set(data.get("activity", {})), nested_fields(ActivityProfile))
                for device in data.get("prior_devices") or []:
                    self.assertLessEqual(set(device), nested_fields(PriorDevice))

    def test_a_spread_of_cases(self):
        cases = [read_case(path) for path in FILES]
        self.assertEqual({c.amputation_level for c in cases}, set(AmputationLevel))  # every level
        self.assertEqual({c.side.value for c in cases}, {"left", "right", "bilateral"})
        self.assertTrue({c.side.value for c in cases if c.is_lower_limb} >= {"left", "right", "bilateral"})
        self.assertTrue({c.side.value for c in cases if not c.is_lower_limb} >= {"left", "right", "bilateral"})
        k_levels = {c.activity.k_level.value if c.activity.k_level else None for c in cases if c.is_lower_limb}
        self.assertEqual(k_levels, {"K0", "K1", "K2", "K3", "K4", "unknown"} | (k_levels & {None}))
        unrecorded = [len(c.unrecorded_fields()) for c in cases]
        self.assertTrue(any(n <= 3 for n in unrecorded), unrecorded)  # nearly complete intakes
        self.assertTrue(any(n >= 10 for n in unrecorded), unrecorded)  # barely filled ones


class LoaderTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.cases_dir = Path(tmp.name) / "cases"
        for patcher in (patch("intake.routes.retrieve_relevant_chunks", side_effect=fake_retrieval),
                        patch.object(store, "folder", self.cases_dir)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_cases_analysed_like_a_submitted_form_and_saved(self):
        records = load(FILES)
        self.assertEqual(sorted(p.stem for p in self.cases_dir.glob("*.json")), [p.stem for p in FILES])
        for record, path in zip(records, FILES):
            with self.subTest(path.name):
                expected = analyse_case(read_case(path))  # what the intake route does
                self.assertEqual([asdict(g) for g in record.gaps], [asdict(g) for g in expected.gaps])
                self.assertEqual([c.statement.id for c in record.shown_statements()],
                                 [c.statement.id for c in expected.shown_statements()])

    def test_review_page_opens_after_loading(self):
        load(FILES[:1])
        store._records.clear()  # as if the app started after the load
        client = create_app().test_client()
        resp = client.get(f"/review/{FILES[0].stem}")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(FILES[0].stem, resp.get_data(as_text=True))

    def test_a_bad_file_stops_before_anything_is_saved(self):
        bad = Path(self.cases_dir.parent) / "trial-99.json"
        data = json.loads(FILES[0].read_text(encoding="utf-8"))  # its case_id is trial-01
        bad.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "must match the file name"):
            load([FILES[1], bad])
        self.assertFalse(self.cases_dir.exists())


if __name__ == "__main__":
    unittest.main()
