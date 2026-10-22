"""Tests for intake/golden_cases.py: the reviewed golden cases, and the checks run on them.

Every golden case marked "reviewed" runs here (statements, supporting
sources, reasoning path, functional level, and for an Arabic or twin case
the intake form and the twin), so a regression fails the normal test run.
Unreviewed cases stay out: only `python -m intake.golden_cases` checks them.
The held-out cases are hashed against their freeze and read for shape, never
analysed: what the app gives for them is seen only in a --held-out run.

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

from intake import golden_cases, routes
from intake.golden_cases import (
    FAIL,
    INFO,
    PASS,
    SKIP,
    WARN,
    case_paths,
    check_case,
    content_hash,
    frozen_problems,
    intake_form,
    main,
    read_golden_case,
    run_case,
    search_unavailable,
    shares_a_run,
)
from intake.routes import analyse_case
from knowledge.models import ProtocolChunk
from reasoning.models import Gap
from shared.config import GOLDEN_CASES_DIR, GOLDEN_HELD_OUT_DIR
from tests.helpers import FakeWriter


def _status(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("review_status")
    except (ValueError, AttributeError):
        return None  # not readable, so not reviewed: only the runner reports it


# Only the reviewed cases: an unreviewed case is a draft, checked by the runner alone.
REVIEWED = [path for path in sorted(GOLDEN_CASES_DIR.glob("*.json")) if _status(path) == "reviewed"]
GOLDEN_01 = GOLDEN_CASES_DIR / "golden-01.json"  # reviewed; the fixtures below start from it
HELD_OUT = sorted(GOLDEN_HELD_OUT_DIR.glob("*.json"))


def no_search(case):
    return {}  # searched, nothing found: every gap without a source


def by_check(findings):
    return {finding.check: finding for finding in findings}


class ReviewedCaseTests(unittest.TestCase):
    """A difference in a reviewed case fails the normal test run."""

    def test_there_are_reviewed_cases(self):
        self.assertIn(GOLDEN_01, REVIEWED)

    def test_every_reviewed_case_decides_every_rule(self):
        for path in REVIEWED:
            with self.subTest(path.name):
                golden = read_golden_case(path)
                self.assertEqual(sorted(golden.present + golden.absent), sorted(golden_cases.RULES))

    def test_every_reviewed_case_still_passes(self):
        # Statements, supporting sources, reasoning path, functional level (and
        # the intake form and twin where the case has them). Gap checks need the
        # search model, so they are SKIPPED here and run in python -m intake.golden_cases.
        for path in REVIEWED:
            with self.subTest(path.name):
                golden, findings = run_case(path, gaps_skipped="unit tests: no search")
                self.assertTrue(golden.reviewed)
                checked = {f.check: f for f in findings if f.status != SKIP}
                self.assertIn("statements", checked)
                self.assertIn("functional level", checked)
                for finding in checked.values():
                    self.assertEqual(finding.status, PASS, f"{finding.check}: {finding.lines}")
                self.assertEqual(by_check(findings)["gaps"].status, SKIP)


class HeldOutTests(unittest.TestCase):
    """The held-out cases: frozen, apart from the development cases, run only with --held-out."""

    def test_the_held_out_cases_are_as_frozen(self):
        self.assertTrue(HELD_OUT)
        self.assertEqual(frozen_problems(), [])

    def test_the_held_out_cases_still_read(self):
        # Shape only (a renamed rule or field would make a frozen case unreadable); never analysed here.
        for path in HELD_OUT:
            with self.subTest(path.name):
                self.assertEqual(read_golden_case(path).id, path.stem)

    def test_no_case_is_in_both_sets(self):
        development = {path.stem for path in GOLDEN_CASES_DIR.glob("*.json")}
        self.assertTrue(development)
        self.assertEqual(development & {path.stem for path in HELD_OUT}, set())

    def test_each_run_takes_its_own_set(self):
        self.assertEqual(case_paths([], held_out=False), sorted(GOLDEN_CASES_DIR.glob("*.json")))
        self.assertEqual(case_paths([], held_out=True), HELD_OUT)

    def test_a_held_out_case_only_with_the_flag(self):
        with self.assertRaises(SystemExit) as stop:
            case_paths([HELD_OUT[0]], held_out=False)
        self.assertIn("run them with --held-out", str(stop.exception))
        with self.assertRaises(SystemExit) as stop:
            case_paths([GOLDEN_01], held_out=True)
        self.assertIn("--held-out runs only the cases in", str(stop.exception))

    def test_the_hash_follows_the_content_not_the_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = json.loads(GOLDEN_01.read_text(encoding="utf-8"))
            one, two, three = (Path(tmp) / f"{n}.json" for n in ("one", "two", "three"))
            one.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
            two.write_text(json.dumps(data, indent=4).replace("\n", "\r\n"), encoding="utf-8")
            data["expected_answer"]["gaps"].pop()
            three.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
            self.assertEqual(content_hash(one), content_hash(two))
            self.assertNotEqual(content_hash(one), content_hash(three))


class ReadingTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.data = json.loads(GOLDEN_01.read_text(encoding="utf-8"))

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
        self.data = json.loads((GOLDEN_CASES_DIR / "golden-02.json").read_text(encoding="utf-8"))  # transfemoral K2
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


class ArabicInterfaceAndTwinTests(unittest.TestCase):
    """A case submitted through the Arabic intake form, checked against its English twin (golden-01)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.twin = json.loads(GOLDEN_01.read_text(encoding="utf-8"))
        (self.folder / "golden-01.json").write_text(json.dumps(self.twin, ensure_ascii=False), encoding="utf-8")

    def arabic_copy(self, change=None) -> Path:
        data = copy.deepcopy(self.twin)
        data.update(id="golden-91", interface_language="ar", twin_of="golden-01", review_status="unreviewed")
        data["question"]["case_id"] = "golden-91"
        data["question"]["residual_limb"]["skin_condition"] = "سليم، ندبة ملتئمة"
        data["question"]["cognitive_status"] = "سليم"
        if change:
            change(data)
        path = self.folder / "golden-91.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path

    def test_the_form_is_filled_in_as_each_interface_would(self):
        question = dict(self.twin["question"], comorbidities=[], prior_devices=[])
        self.assertEqual(intake_form(question, "ar")["comorbidities"], "لا يوجد")
        self.assertEqual(intake_form(question, "en")["comorbidities"], "none")
        self.assertEqual(intake_form(question, "ar")["no_prior_devices"], "on")
        devices = dict(question, comorbidities=["a", "b"], prior_devices=[
            {"device_description": "PTB socket", "years_used": 2, "currently_using": False, "issues": None}])
        form = intake_form(devices, "ar")
        self.assertEqual((form["comorbidities"], form["device_1_description"], form["device_1_years"],
                          form["device_1_current"], form["device_1_issues"]), ("a\nb", "PTB socket", "2", "no", ""))
        self.assertNotIn("no_prior_devices", form)

    def test_arabic_submission_matching_its_twin_passes(self):
        cases_folder, store_before, search_before = routes.store.folder, routes.store, routes.retrieve_relevant_chunks
        golden, findings = run_case(self.arabic_copy(), gaps_skipped="test: no search")
        found = by_check(findings)
        self.assertEqual(found["intake form"].status, PASS, found["intake form"].lines)
        self.assertEqual(found["twin"].status, PASS, found["twin"].lines)
        self.assertEqual(found["statements"].status, PASS)
        # The route's store and search were put back; nothing was saved to the case folder.
        self.assertIs(routes.store, store_before)
        self.assertEqual(routes.store.folder, cases_folder)
        self.assertIs(routes.retrieve_relevant_chunks, search_before)

    def test_a_field_the_form_cannot_carry_is_reported(self):
        def notes(data):
            data["question"]["residual_limb"]["notes"] = "no form input for this"
        found = by_check(run_case(self.arabic_copy(notes), gaps_skipped="test: no search")[1])
        self.assertEqual(found["intake form"].status, WARN)
        self.assertTrue(any(line.startswith("residual_limb:") for line in found["intake form"].lines))

    def test_a_different_analysis_from_the_twin_is_reported(self):
        def k2(data):
            data["question"]["activity"]["k_level"] = "K2"
        found = by_check(run_case(self.arabic_copy(k2), gaps_skipped="test: no search")[1])
        self.assertEqual(found["intake form"].status, PASS)  # the form took it as written
        self.assertEqual(found["twin"].status, WARN)
        self.assertTrue(any(line.startswith("statements:") for line in found["twin"].lines))
        self.assertTrue(any(line.startswith("functional level:") for line in found["twin"].lines))
        reviewed = self.arabic_copy(lambda d: (k2(d), d.update(review_status="reviewed")))
        self.assertEqual(by_check(run_case(reviewed, gaps_skipped="test: no search")[1])["twin"].status, FAIL)

    def test_gap_sources_are_compared_when_the_search_ran(self):
        golden = read_golden_case(self.arabic_copy())
        record = analyse_case(golden.case, retrieve=no_search)
        chunk = ProtocolChunk("lower_limb_amputation_va_dod_cpg_2024-0101", "pain", "g.pdf", "VA/DoD", 2024, 101)
        record.gaps[1].evidence = chunk  # as if this case had cited a passage its twin did not
        with mock.patch.object(golden_cases, "analyse_case", side_effect=lambda case, retrieve=None, writer=None:
                               analyse_case(case, retrieve=no_search, writer=writer)):
            finding = golden_cases.compare_with_twin(golden, record, gaps_skipped=None)
        self.assertEqual(finding.status, WARN)
        self.assertTrue(any(line.startswith("gap sources:") for line in finding.lines))

    def test_bad_language_or_twin_refused(self):
        for change in (lambda d: d.update(interface_language="fr"), lambda d: d.update(twin_of="golden-91"),
                       lambda d: d.update(twin_of="golden-99")):
            with self.subTest(change), self.assertRaises(ValueError):
                read_golden_case(self.arabic_copy(change))


class RagMeasureTests(unittest.TestCase):
    """--rag: the RAG measured against the answer key, with a fake writer (no API calls)."""

    def test_shares_a_run_of_words(self):
        statement = "For prosthetic ambulators, we suggest prescribing microprocessor knee units over others."
        self.assertTrue(shares_a_run("we suggest prescribing microprocessor knee units", statement))
        self.assertTrue(shares_a_run("We suggest PRESCRIBING microprocessor knee units today", statement))
        self.assertFalse(shares_a_run("we suggest prescribing a knee unit", statement))
        self.assertFalse(shares_a_run("", statement))

    def test_coverage_and_must_not_show(self):
        golden = read_golden_case(GOLDEN_CASES_DIR / "golden-02.json")  # transfemoral K2
        present = golden_cases.RULES["va_dod_ll_17_microprocessor_knee"].statement
        absent = golden_cases.RULES["icrc_tt_ptb_socket"].statement  # transtibial only
        self.assertIn(present.id, golden.present)
        self.assertIn(absent.id, golden.absent)

        def passage(statement, n):
            return ProtocolChunk(f"{statement.doc_id}-090{n}", statement.quote.text, "x.pdf", "T", 2024,
                                 statement.quote.page, statement.quote.page)

        passages = {"knee": [passage(present, 1)], "socket": [passage(absent, 2)]}
        record = analyse_case(golden.case, retrieve=lambda case: passages, writer=FakeWriter())
        found = by_check(check_case(golden, record, gaps_skipped="test: no search", rag=True))
        coverage = found["rag coverage"]
        self.assertEqual(coverage.status, INFO)
        expected = len(golden.present) + 1  # and the functional level's description
        self.assertEqual(coverage.numbers, {"expected": expected, "covered": 1})
        self.assertIn(f"not covered: {golden.data['expected_answer']['functional_level']}", coverage.lines)
        self.assertNotIn(f"not covered: {present.id}", coverage.lines)
        must_not = found["rag must-not-show"]
        self.assertEqual(must_not.status, WARN)
        self.assertTrue(any(line.startswith(f"{absent.id}: by rag-socket-") for line in must_not.lines))
        answer = found["rag answer"]
        self.assertEqual((answer.status, answer.numbers["kept"], answer.numbers["removed"]), (INFO, 2, 0))
        self.assertIn("1 match no expected statement", answer.lines[0])
        flags = found["rag sentence flags"]  # the fake writer's sentences name no number, code, level or advice
        self.assertEqual((flags.status, flags.numbers), (INFO, {"flagged": 0}))
        self.assertIn("0 of 2 kept items flagged", flags.lines[0])
        # The answer key's own checks still pass: the RAG is measured, never failed.
        self.assertEqual(found["statements"].status, PASS)

    def test_rag_needs_the_search(self):
        with self.assertRaises(SystemExit) as stop:
            main([str(GOLDEN_01), "--rag", "--no-search"])
        self.assertIn("--rag needs the search", str(stop.exception))


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

    def test_no_search_run_of_the_reviewed_cases(self):
        status, text = self.run_main([*map(str, REVIEWED), "--no-search"])
        self.assertEqual(status, 0)
        self.assertIn("Gap checks SKIPPED: skipped with --no-search", text)
        self.assertIn(f"{len(REVIEWED)} case(s):", text)
        self.assertIn(" 0 FAIL", text)

    def test_exit_status_1_on_fail_or_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = json.loads((GOLDEN_CASES_DIR / "golden-03.json").read_text(encoding="utf-8"))
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

    def frozen_copy(self) -> tuple[Path, Path]:
        """A temporary held-out folder with golden-03 frozen in it: the real held-out cases aren't run here."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        folder = Path(tmp.name) / "held_out"
        folder.mkdir()
        case = folder / "golden-03.json"
        case.write_text((GOLDEN_CASES_DIR / "golden-03.json").read_text(encoding="utf-8"), encoding="utf-8")
        manifest = Path(tmp.name) / "held_out.json"
        manifest.write_text(json.dumps({"cases": {"golden-03": {"sha256": content_hash(case),
                                                                "frozen_on": "2026-10-13"}}}), encoding="utf-8")
        for name, value in (("GOLDEN_HELD_OUT_DIR", folder), ("GOLDEN_HELD_OUT_MANIFEST", manifest)):
            patcher = mock.patch.object(golden_cases, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        return folder, case

    def test_held_out_run_only_as_frozen(self):
        folder, case = self.frozen_copy()
        status, text = self.run_main(["--held-out", "--no-search"])
        self.assertEqual(status, 0)
        self.assertIn("HELD-OUT run: 1 frozen case(s)", text)
        self.assertIn("golden-03  [reviewed]", text)
        data = json.loads(case.read_text(encoding="utf-8"))
        case.write_text(json.dumps(data, indent=4), encoding="utf-8")  # layout only: still as frozen
        self.assertEqual(self.run_main(["--held-out", "--no-search"])[0], 0)

        data["expected_answer"]["gaps"].pop()
        case.write_text(json.dumps(data), encoding="utf-8")
        (folder / "golden-98.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(SystemExit) as stop:
            self.run_main(["--held-out", "--no-search"])
        message = str(stop.exception)
        self.assertIn("nothing was run", message)
        self.assertIn("golden-03: changed since it was frozen on 2026-10-13", message)
        self.assertIn("golden-98: in ", message)
        case.unlink()
        with self.assertRaises(SystemExit) as stop:
            self.run_main(["--held-out", "--no-search"])
        self.assertIn("golden-03: frozen in ", str(stop.exception))


if __name__ == "__main__":
    unittest.main()
