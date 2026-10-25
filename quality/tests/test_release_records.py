"""Tests for what the quality page reads (plan Part 4, 2026-10-25): the recorded results (quality/results.py), the
owner's release sign-offs (quality/releases.py) and the measures and audit trail built from them
(quality/measures.py). Nothing here writes to the real data/quality/ files."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from knowledge.clinic_rules import ClinicRule
from quality import golden_cases, measures, results
from quality.releases import COLUMNS, Release, latest_release, load_releases
from shared.config import GOLDEN_CASES_DIR


class RecordedResultsTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "results" / "runs.jsonl"

    def test_a_run_is_added_with_its_time_and_versions(self):
        self.assertEqual(results.read_runs(self.path), [])
        first = results.record_run(results.RELEASE_CHECK, {"steps": {"unit tests": "OK"}}, self.path)
        results.record_run(results.GOLDEN_CASES, {"set": results.HELD_OUT, "mode": results.SEARCH, "cases": 5,
                                                  "passed": 5}, self.path)
        runs = results.read_runs(self.path)
        self.assertEqual([run["kind"] for run in runs], [results.RELEASE_CHECK, results.GOLDEN_CASES])
        self.assertTrue(first["recorded_at"].endswith("+00:00"))
        self.assertEqual(set(first["versions"]), {"model", "prompts", "library"})
        self.assertEqual(set(first["versions"]["prompts"]), {"prosthetics", "orthotics"})
        self.assertEqual(results.latest(runs, results.GOLDEN_CASES, set=results.HELD_OUT)["passed"], 5)
        self.assertIsNone(results.latest(runs, results.GOLDEN_CASES, set=results.DEVELOPMENT))
        with self.assertRaises(ValueError):
            results.record_run("made_up", {}, self.path)

    def test_a_golden_case_run_records_itself_only_when_asked(self):
        reviewed = [GOLDEN_CASES_DIR / "golden-01.json"]
        with patch.object(results.config, "QUALITY_RESULTS_PATH", self.path), \
                contextlib.redirect_stdout(io.TextIOWrapper(io.BytesIO(), encoding="utf-8")):
            golden_cases.main([str(reviewed[0]), "--no-search"])
            self.assertFalse(self.path.exists())
            golden_cases.main([str(reviewed[0]), "--no-search", "--record"])
        [run] = results.read_runs(self.path)
        self.assertEqual((run["kind"], run["set"], run["mode"], run["cases"], run["passed"], run["failed_cases"]),
                         (results.GOLDEN_CASES, results.DEVELOPMENT, results.NO_SEARCH, 1, 1, []))


class ReleaseSignOffTests(unittest.TestCase):
    def write(self, *rows) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "releases.csv"
        path.write_text("\n".join([",".join(COLUMNS), *rows]) + "\n", encoding="utf-8")
        return path

    def test_the_project_file_reads(self):
        load_releases()  # the owner's file: valid (it may have no row yet)

    def test_rows_and_their_checks(self):
        path = self.write("2026-10-25,,,,,", "", "rc2,Owner,2026-10-26,Arabic reader,2026-10-26,first trial")
        releases = load_releases(path)
        self.assertEqual([r.release for r in releases], ["2026-10-25", "rc2"])
        self.assertFalse(releases[0].signed_off)
        self.assertTrue(latest_release(path).signed_off and latest_release(path).arabic_checked)
        for row in ("rc,Owner,,,,", "rc,,2026-10-26,,,", "rc,Owner,26/10/2026,,,", ",Owner,2026-10-26,,,",
                    "rc,,,,,,extra"):
            with self.subTest(row), self.assertRaises(ValueError):
                load_releases(self.write(row))
        self.assertIsNone(latest_release(Path(self.write().parent) / "missing.csv"))


class MeasureTests(unittest.TestCase):
    def test_the_share_the_quote_check_removed(self):
        files = [{"generation": {"parts": {"gaps": {"items": [{}, {}], "removed": [{"dropped": "item"}]},
                                           "components": {"items": [{}], "removed": [{"dropped": "repeat"},
                                                                                     {"dropped": "grade"}]}}}},
                 {"generation": None}]
        counts = measures.quote_check_counts(files)
        self.assertEqual(counts, {"cases": 1, "kept": 3, "removed": 1})
        self.assertEqual(measures.share(counts["removed"], counts["kept"] + counts["removed"]), 25)
        self.assertIsNone(measures.share(0, 0))

    def test_summary_wrong_marks_counted_from_version_11(self):
        def entry(version, *marks, decision="approve"):
            return {"log_version": version, "decision": decision, "fitting": {"sections": [
                {"statements": [{"reviewer_judgement": mark} for mark in marks]}]}}
        entries = [entry(10, "relevant"), entry(11, "summary_wrong", "relevant", None),
                   entry(11, "summary_wrong", decision="design_choice")]
        self.assertEqual(measures.summary_wrong_counts(entries), {"decisions": 1, "marked": 2, "wrong": 1})

    def test_the_release_gate_reads_only_what_was_recorded(self):
        empty = measures.release_gate([], None)
        self.assertEqual([empty[k]["state"] for k in ("tests", "held_out", "arabic", "sign_off")],
                         ["not_recorded", "not_recorded", "not_recorded", "awaiting"])
        runs = [{"kind": results.RELEASE_CHECK, "recorded_at": "t1", "unit_tests": {"ok": True, "ran": 600}},
                {"kind": results.GOLDEN_CASES, "set": results.HELD_OUT, "recorded_at": "t2", "passed": 4, "cases": 5}]
        release = Release("rc1", "Owner", "2026-10-26", "", "", "")
        gate = measures.release_gate(runs, release)
        self.assertEqual((gate["tests"]["state"], gate["tests"]["ran"]), ("pass", 600))
        self.assertEqual((gate["held_out"]["state"], gate["held_out"]["passed"]), ("fail", 4))
        self.assertEqual(gate["arabic"]["state"], "not_recorded")
        self.assertEqual((gate["sign_off"]["state"], gate["sign_off"]["by"]), ("pass", "Owner"))

    def test_the_audit_trail_is_newest_first_and_names_no_one(self):
        entries = [{"logged_at": "2026-10-25T10:00:00+00:00", "decision": "approve", "case_id": "c1",
                    "domain": "prosthetics", "versions": {"prompt": "rag-v3", "library": {"built": "2026-10-22"}}},
                   {"logged_at": "2026-10-23T09:00:00+00:00", "decision": "design_choice", "case_id": "c2",
                    "generation": {"prompt_version": "rag-ort-v2"}}]
        runs = [{"kind": results.GOLDEN_CASES, "recorded_at": "2026-10-24T08:00:00+00:00", "set": results.DEVELOPMENT,
                 "mode": results.NO_SEARCH, "passed": 11, "cases": 11, "versions": {"prompts": {"p": "rag-v3"}}}]
        rule = ClinicRule("open_wound", "prosthetics", "hard_stop", "approved", 2, "Owner", "2026-10-26", "design")
        rows = measures.audit_rows(entries, runs, {"built": "2026-10-22T19:01:20+00:00", "passages": 4890}, [rule],
                                   [Release("rc1", "Owner", "2026-10-27", "", "", "")])
        self.assertEqual([row["what"] for row in rows],
                         ["signed_off", "rule_approved", "decision", "golden_development", "design_choice", "library"])
        self.assertEqual(rows[2]["versions"], {"prompt": "rag-v3", "library": "2026-10-22"})
        self.assertEqual(rows[4]["versions"]["prompt"], "rag-ort-v2")  # an older line: from its generation
        self.assertFalse(any("who" in row for row in rows))


if __name__ == "__main__":
    unittest.main()
