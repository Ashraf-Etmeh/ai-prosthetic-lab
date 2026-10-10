"""Tests for intake/golden_cases.py: the golden-case files and the checks run on them.

No embedding model: the search is replaced (analyse_case's `retrieve`), and
gap sources come from fake passages.
"""

import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from intake import golden_cases
from intake.golden_cases import (
    FAIL,
    PASS,
    SKIP,
    WARN,
    check_case,
    main,
    read_golden_case,
    run_case,
    search_unavailable,
)
from intake.routes import analyse_case
from knowledge.models import ProtocolChunk
from reasoning.models import Gap
from shared.config import GOLDEN_CASES_DIR

CASE_FILES = sorted(GOLDEN_CASES_DIR.glob("*.json"))


def no_search(case):
    return {}  # searched, nothing found: every gap without a source


def by_check(findings):
    return {finding.check: finding for finding in findings}


class GoldenFileTests(unittest.TestCase):
    def test_the_case_files_are_valid(self):
        self.assertEqual([path.stem for path in CASE_FILES], ["golden-01", "golden-02", "golden-03"])
        for path in CASE_FILES:
            with self.subTest(path.name):
                golden = read_golden_case(path)
                self.assertIn(golden.data["review_status"], golden_cases.REVIEW_STATUSES)
                # Every component and fitting rule is decided one way or the other.
                self.assertEqual(sorted(golden.present + golden.absent), sorted(golden_cases.RULES))

    def test_the_case_files_run_without_the_model(self):
        # A reviewed case fails on any difference, so this guards the statements
        # and functional level of every reviewed case.
        for path in CASE_FILES:
            with self.subTest(path.name):
                golden, findings = run_case(path, gaps_skipped="test: no search")
                statuses = {finding.check: finding.status for finding in findings}
                self.assertNotIn(FAIL, statuses.values())
                self.assertEqual(statuses["gaps"], SKIP)
                self.assertIn("statements", statuses)


class ReadingTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.data = json.loads(CASE_FILES[0].read_text(encoding="utf-8"))

    def write(self, data, name="golden-01") -> Path:
        path = self.folder / f"{name}.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def refused(self, change, name="golden-01"):
        data = copy.deepcopy(self.data)
        change(data)
        with self.assertRaises(ValueError) as error:
            read_golden_case(self.write(data, name))
        return str(error.exception)

    def test_a_valid_copy_reads(self):
        self.assertEqual(read_golden_case(self.write(self.data)).id, "golden-01")

    def test_malformed_files_are_refused(self):
        statement = self.data["expected_answer"]["statements_present"][0]
        changes = {
            "unknown key": lambda d: d.update(notes="x"),
            "missing key": lambda d: d.pop("reasoning_path"),
            "review status": lambda d: d.update(review_status="draft"),
            "criterion": lambda d: d.update(evaluation_criteria=["statements", "speed"]),
            "no criteria": lambda d: d.update(evaluation_criteria=[]),
            "question not to_dict": lambda d: d["question"].pop("intake_notes"),
            "question case_id": lambda d: d["question"].update(case_id="other"),
            "unknown statement": lambda d: d["expected_answer"]["statements_present"].append("no_such_rule"),
            "repeated statement": lambda d: d["expected_answer"]["statements_present"].append(statement),
            "present and absent": lambda d: d["common_wrong_answers"]["statements_absent"].append(statement),
            "gap field": lambda d: d["expected_answer"]["gaps"].append({"field": "shoe_size", "source_expected": None}),
            "source_expected": lambda d: d["expected_answer"]["gaps"][0].update(source_expected="yes"),
            "functional level": lambda d: d["expected_answer"].update(functional_level="cms_k9_description"),
            "catalog id": lambda d: d["supporting_sources"].append("no_such_document"),
            "reasoning not for every statement": lambda d: d["reasoning_path"].pop(statement),
            "reasoning expected": lambda d: d["reasoning_path"][statement].update(expected="absent"),
            "reasoning field": lambda d: d["reasoning_path"][statement]["decided_by"].append(
                {"field": "age", "case_value": 45}),
            "reasoning empty": lambda d: d["reasoning_path"][statement].update(decided_by=[]),
        }
        for name, change in changes.items():
            with self.subTest(name):
                self.assertTrue(self.refused(change).startswith("golden-01.json: "))
        with self.subTest("id must be the file name"):
            self.refused(lambda d: None, name="golden-99")


class CheckTests(unittest.TestCase):
    """The checks against a record from analyse_case, with the search replaced."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.data = json.loads(CASE_FILES[1].read_text(encoding="utf-8"))  # transfemoral K2
        self.data["review_status"] = "unreviewed"  # mismatches WARN; the tests that need FAIL set "reviewed"

    def golden(self, change=None):
        data = copy.deepcopy(self.data)
        if change:
            change(data)
        path = self.folder / "golden-02.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return read_golden_case(path)

    def check(self, golden, retrieve=no_search, extra_gaps=()):
        record = analyse_case(golden.case, retrieve=retrieve)
        record.gaps.extend(extra_gaps)
        return by_check(check_case(golden, record))

    def test_matching_draft_passes(self):
        findings = self.check(self.golden(lambda d: [g.update(source_expected=False)
                                                     for g in d["expected_answer"]["gaps"]]))
        self.assertEqual({f.status for f in findings.values()}, {PASS})

    def test_statement_differences_are_named(self):
        def move(d):  # a statement the rules show, drafted as absent; one they hide, drafted as present
            d["expected_answer"]["statements_present"].remove("cms_k2_microprocessor_knee")
            d["common_wrong_answers"]["statements_absent"].append("cms_k2_microprocessor_knee")
            d["common_wrong_answers"]["statements_absent"].remove("icrc_tt_ptb_socket")
            d["expected_answer"]["statements_present"].append("icrc_tt_ptb_socket")
            d["reasoning_path"]["cms_k2_microprocessor_knee"]["expected"] = "absent"
            d["reasoning_path"]["icrc_tt_ptb_socket"]["expected"] = "present"
        finding = self.check(self.golden(move))["statements"]
        self.assertEqual(finding.status, WARN)
        self.assertIn("missing: icrc_tt_ptb_socket", finding.lines)
        self.assertIn("unexpected: cms_k2_microprocessor_knee (listed in statements_absent)", finding.lines)

    def test_a_reviewed_case_fails_where_an_unreviewed_one_warns(self):
        def wrong_level(d):
            d["expected_answer"]["functional_level"] = "cms_k3_description"
        self.assertEqual(self.check(self.golden(wrong_level))["functional level"].status, WARN)
        reviewed = self.golden(lambda d: (wrong_level(d), d.update(review_status="reviewed")))
        finding = self.check(reviewed)["functional level"]
        self.assertEqual(finding.status, FAIL)
        self.assertEqual(finding.lines, ["expected cms_k3_description, shown cms_k2_description"])

    def test_supporting_sources_compared_with_the_statements_shown(self):
        finding = self.check(self.golden(lambda d: d.update(supporting_sources=[
            "lower_limb_amputation_va_dod_cpg_2024", "upper_limb_amputation_va_dod_cpg_2022"])))["supporting sources"]
        self.assertEqual(finding.status, WARN)
        self.assertIn("missing: upper_limb_amputation_va_dod_cpg_2022", finding.lines)
        self.assertIn("unexpected: prosthetic_gait_analysis_icrc_manual_2014", finding.lines)

    def test_reasoning_path_checked_against_the_rules_and_the_case(self):
        def wrong(d):
            path = d["reasoning_path"]
            path["cms_k2_microprocessor_knee"]["decided_by"] = [{"field": "levels", "case_value": "transfemoral"}]
            path["icrc_tf_check_socket"]["decided_by"].append({"field": "ambulators_only", "case_value": "K2"})
            path["icrc_tt_ptb_socket"]["decided_by"][0]["case_value"] = "transtibial"
        finding = self.check(self.golden(wrong))["reasoning path"]
        self.assertEqual(finding.status, WARN)
        self.assertEqual(finding.lines[1:], [  # in the file's order
            "cms_k2_microprocessor_knee: present, but its rule also sets k_levels",
            "icrc_tt_ptb_socket: levels reads 'transfemoral', written as 'transtibial'",
            "icrc_tf_check_socket: the rule doesn't set ambulators_only",
        ])

    def test_gap_differences(self):
        def change(d):
            gaps = d["expected_answer"]["gaps"]
            gaps[0]["source_expected"] = True  # none is cited by no_search
            gaps.pop()  # body_weight_kg: shown, not expected
            gaps.append({"field": "etiology", "source_expected": None})  # recorded, so no gap
        finding = self.check(self.golden(change))["gaps"]
        self.assertEqual(finding.status, WARN)
        self.assertIn("missing: etiology", finding.lines)
        self.assertIn("unexpected: body_weight_kg", finding.lines)
        self.assertIn("source: residual_limb.volume_stability: source expected, none cited", finding.lines)

    def test_a_gap_citing_an_excluded_document_always_fails(self):
        chunk = ProtocolChunk("prosthetic_gait_analysis_icrc_manual_2014-0012", "text", "manual.pdf", "ICRC", 2014, 20)
        gap = Gap("intake_notes", "Notes", "not recorded", "why", chunk.chunk_id, chunk, "text")
        findings = self.check(self.golden(), extra_gaps=[gap])
        self.assertEqual(findings["excluded documents"].status, FAIL)  # though the case is unreviewed
        self.assertIn("intake_notes: prosthetic_gait_analysis_icrc_manual_2014-0012", findings["excluded documents"].lines)

    def test_gaps_skipped_without_the_search(self):
        golden = self.golden()
        record = analyse_case(golden.case, retrieve=golden_cases._not_searched("no model here"))
        finding = by_check(check_case(golden, record, "no model here"))["gaps"]
        self.assertEqual((finding.status, finding.lines), (SKIP, ["no model here"]))
        self.assertNotIn("excluded documents", by_check(check_case(golden, record, "no model here")))

    def test_only_the_listed_criteria_run(self):
        findings = self.check(self.golden(lambda d: d.update(evaluation_criteria=["functional_level"])))
        self.assertEqual(list(findings), ["functional level"])


class SearchAvailabilityTests(unittest.TestCase):
    def test_reasons_without_loading_the_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp)
            self.assertIn("python -m knowledge.ingest", search_unavailable(store))
            (store / "info.json").write_text(json.dumps({"model": "other/model", "revision": "1"}), encoding="utf-8")
            self.assertIn("built with other/model", search_unavailable(store))
            (store / "info.json").write_text(json.dumps({"model": golden_cases.EMBEDDING_MODEL_NAME,
                                                         "revision": golden_cases.EMBEDDING_MODEL_REVISION}),
                                             encoding="utf-8")
            with mock.patch("huggingface_hub.try_to_load_from_cache", return_value=None):
                self.assertIn("not in the local Hugging Face cache", search_unavailable(store))
            with mock.patch("huggingface_hub.try_to_load_from_cache", return_value="/cache/config.json"):
                self.assertIsNone(search_unavailable(store))


class CommandTests(unittest.TestCase):
    def run_main(self, argv):
        out = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        with contextlib.redirect_stdout(out):
            status = main(argv)
        out.flush()
        return status, out.buffer.getvalue().decode("utf-8")

    def test_no_search_run_of_the_case_files(self):
        status, text = self.run_main(["--no-search"])
        self.assertEqual(status, 0)
        self.assertIn("Gap checks SKIPPED: skipped with --no-search", text)
        self.assertIn("3 case(s):", text)

    def test_exit_status_1_on_fail_or_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = json.loads(CASE_FILES[2].read_text(encoding="utf-8"))
            data["review_status"] = "reviewed"
            data["expected_answer"]["functional_level"] = "cms_k1_description"
            reviewed = Path(tmp) / "golden-03.json"
            reviewed.write_text(json.dumps(data), encoding="utf-8")
            status, text = self.run_main([str(reviewed), "--no-search"])
            self.assertEqual(status, 1)
            self.assertIn("FAIL  functional level   expected cms_k1_description, shown none", text)
            broken = Path(tmp) / "golden-04.json"
            broken.write_text("{", encoding="utf-8")
            status, text = self.run_main([str(broken), "--no-search"])
            self.assertEqual(status, 1)
            self.assertIn("ERROR case file", text)


if __name__ == "__main__":
    unittest.main()
