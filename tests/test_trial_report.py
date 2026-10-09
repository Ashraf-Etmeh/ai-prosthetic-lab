"""Tests for review/trial_report.py on a small fake review log."""

import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

from reasoning.component_support import component_support
from reasoning.fitting_support import fitting_support
from reasoning.gap_analysis import analyze_gaps
from review.decision_log import record_decision
from review.trial_report import build_report, print_summary, read_log, write_csv
from shared.case_schema import Case
from shared.store import CaseRecord
from tests.test_store import VOLUME_PASSAGE

VOLUME = "residual_limb.volume_stability"  # shown with a source passage in these cases
WOUND = "residual_limb.wound_status"  # shown without one
PAIN = "residual_limb.pain"


def record(case_id: str, level: str) -> CaseRecord:
    case = Case(amputation_level=level, side="left", case_id=case_id)
    chunks = {VOLUME: [VOLUME_PASSAGE]}
    return CaseRecord(case=case, retrieved_chunks=chunks, gaps=analyze_gaps(case, chunks),
                      components=component_support(case), fitting=fitting_support(case))


def fake_log(path: Path) -> None:
    """Five decisions on three cases, written by the app's own logger, plus one old-format line."""
    tt, tr, tf = record("case-tt", "transtibial"), record("case-tr", "transradial"), record("case-tf", "transfemoral")
    record_decision(tt, "approve", path=path, gap_judgements={VOLUME: "needed", WOUND: "needed", PAIN: "not_needed"},
                    statement_judgements={"icrc_ready_for_fitting": "relevant", "cms_elevated_vacuum": "not_relevant"})
    record_decision(tt, "edit", note="Volume was measured at the clinic.", path=path,
                    gap_judgements={VOLUME: "not_needed"}, statement_judgements={"icrc_ready_for_fitting": "relevant"})
    record_decision(tr, "reject", path=path, gap_judgements={WOUND: "needed"},
                    statement_judgements={"va_dod_ul_8_no_specific_component": "relevant"})
    record_decision(tf, "edit", note="يجب إضافة قياس الطول", path=path, ui_language="ar")
    # A version-2 line (a copy of the first decision, so with its gap marks): no component or fitting marks yet.
    old = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    for key in ("components", "fitting"):
        del old[key]
    old.update(log_version=2, case_id="case-old", decision="approve")
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(old, ensure_ascii=False) + "\n")


def sections(path: Path) -> dict[str, list[list[str]]]:
    """The report CSV as {section title: [header, rows...]}."""
    result, title = {}, None
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.reader(f):
            if row and row[0].startswith("# "):
                title = row[0][2:]
                result[title] = []
            elif row:
                result[title].append(row)
    return result


class TrialReportTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.log = Path(tmp.name) / "review_log.jsonl"
        self.out = Path(tmp.name) / "trial" / "report.csv"
        fake_log(self.log)
        self.report = build_report(read_log(self.log), self.log)

    def test_totals(self):
        r = self.report
        self.assertEqual((r.decisions, len(r.cases)), (5, 4))
        self.assertEqual(sum(1 for n in r.cases.values() if n > 1), 1)  # case-tt decided twice
        self.assertEqual(dict(r.decision_counts), {"approve": 2, "edit": 2, "reject": 1})
        self.assertEqual(dict(r.log_versions), {4: 4, 2: 1})

    def test_gap_marks_split_by_source(self):
        rows = {(f, src): (needed, not_needed, unmarked)
                for f, _, src, needed, not_needed, unmarked in self.report.gap_rows()}
        # Volume (source shown): needed in the approve and the old copy of it, not needed in the edit.
        self.assertEqual(rows[(VOLUME, "yes")], (2, 1, 2))
        self.assertEqual(rows[(WOUND, "no")], (3, 0, 2))
        self.assertEqual(rows[(PAIN, "no")], (0, 2, 3))
        self.assertNotIn((WOUND, "yes"), rows)  # never shown with a source here
        # Rows follow the field guide, not the counts.
        fields = [f for f, *_ in self.report.gap_rows()]
        self.assertLess(fields.index(WOUND), fields.index(VOLUME))

    def test_unsourced_gaps_marked_needed(self):
        self.assertEqual(self.report.unsourced_rows(),
                         [(WOUND, "Residual limb wound status", 3, "case-tt case-tr case-old")])

    def test_statement_marks(self):
        rows = {s: (part, section, relevant, not_relevant, unmarked)
                for s, part, section, _, relevant, not_relevant, unmarked in self.report.statement_rows()}
        self.assertEqual(rows["icrc_ready_for_fitting"], ("fitting", "readiness", 2, 0, 1))  # tt twice, tf unmarked
        self.assertEqual(rows["cms_elevated_vacuum"], ("components", "suspension", 0, 1, 2))
        self.assertEqual(rows["va_dod_ul_8_no_specific_component"], ("components", "control_and_fit", 1, 0, 0))

    def test_edit_notes_as_written(self):
        notes = [(case_id, lang, note) for _, case_id, lang, note in self.report.edit_notes]
        self.assertEqual(notes, [("case-tt", "en", "Volume was measured at the clinic."),
                                 ("case-tf", "ar", "يجب إضافة قياس الطول")])

    def test_csv_sections(self):
        write_csv(self.report, self.out)
        report = sections(self.out)
        self.assertEqual(list(report), ["Trial report (counts only)", "Gap fields",
                                        "Gaps shown without a source and marked Needed", "Statements",
                                        "Decisions", "Edit notes"])
        self.assertIn(["decisions logged", "5"], report["Trial report (counts only)"])
        self.assertEqual(report["Gap fields"][0],
                         ["field", "label", "source passage shown", "needed", "not needed", "not marked"])
        self.assertIn([VOLUME, "Residual limb volume stability", "yes", "2", "1", "2"], report["Gap fields"])
        self.assertEqual(report["Decisions"][1:], [["approve", "2"], ["edit", "2"], ["reject", "1"]])
        self.assertEqual(report["Edit notes"][2][3], "يجب إضافة قياس الطول")
        text = self.out.read_text(encoding="utf-8-sig").lower()
        for word in ("score", "%", "rank"):  # counts only
            self.assertNotIn(word, text)

    def test_summary(self):
        out = io.StringIO()
        print_summary(self.report, out)
        text = out.getvalue()
        self.assertIn("5 decisions on 4 cases (1 cases decided more than once)", text)
        self.assertIn("Decisions: approve 2, edit 2, reject 1", text)
        self.assertRegex(text, r"residual_limb.wound_status\s+3\s+case-tt case-tr case-old")
        self.assertIn("[ar]  يجب إضافة قياس الطول", text)

    def test_empty_or_missing_log(self):
        report = build_report(read_log(self.log.parent / "missing.jsonl"))
        out = io.StringIO()
        print_summary(report, out)
        self.assertIn("No decisions logged yet.", out.getvalue())
        write_csv(report, self.out)
        self.assertEqual(sections(self.out)["Decisions"][1:], [["approve", "0"], ["edit", "0"], ["reject", "0"]])


if __name__ == "__main__":
    unittest.main()
