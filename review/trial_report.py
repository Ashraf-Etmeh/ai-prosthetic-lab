"""Trial report: how the reviewers marked what the review pages showed, as counts.

  python -m review.trial_report [--log data/review_log.jsonl] [--out data/trial/report.csv]

Reads every decision in the review log and counts:
- per gap field: marked Needed / Not needed / not marked, separately for
  gaps shown with a source passage and gaps shown without one,
- gaps shown without a source that were marked Needed (where the library
  may lack a source), with their case ids,
- per component or fitting statement: Relevant / Not relevant / not marked,
- decisions (approve / edit / reject), and every edit note as written.

Each logged decision counts once: a case decided twice counts twice (the
summary says how many cases were). Counts only: no scores, percentages,
rankings or conclusions. Rows follow the field guide and the statement
guides, never the counts. Lines from older log versions are read too; they
simply have no component or fitting marks.
"""

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from reasoning import component_guide, fitting_guide
from shared.config import REVIEW_LOG_PATH, TRIAL_DIR
from shared.field_guide import FIELDS

REPORT_PATH = TRIAL_DIR / "report.csv"
DECISIONS = ("approve", "edit", "reject")
MARKS = {"gap": ("needed", "not_needed", None), "statement": ("relevant", "not_relevant", None)}
GUIDE_ORDER = [s.id for s in (*component_guide.ALL_STATEMENTS, *fitting_guide.ALL_STATEMENTS)]
FIELD_ORDER = [info.path for info in FIELDS]


@dataclass
class TrialReport:
    log_path: Path
    decisions: int = 0
    cases: Counter = field(default_factory=Counter)  # case id -> decisions logged
    log_versions: Counter = field(default_factory=Counter)
    first_logged: str = ""
    last_logged: str = ""
    # (gap field, shown with a source?) -> Counter of marks; None = not marked
    gap_marks: dict = field(default_factory=lambda: defaultdict(Counter))
    gap_labels: dict = field(default_factory=dict)
    # gap field -> case ids, once per decision: shown without a source, marked Needed
    unsourced_needed: dict = field(default_factory=lambda: defaultdict(list))
    # statement id -> Counter of marks; and (part, section, source document) per id
    statement_marks: dict = field(default_factory=lambda: defaultdict(Counter))
    statement_info: dict = field(default_factory=dict)
    decision_counts: Counter = field(default_factory=Counter)
    edit_notes: list = field(default_factory=list)  # (logged at, case id, page language, note)

    def gap_rows(self) -> list[tuple]:
        keys = sorted(self.gap_marks, key=lambda k: (_order(FIELD_ORDER, k[0]), not k[1]))
        return [(f, self.gap_labels.get(f, ""), "yes" if sourced else "no",
                 *(self.gap_marks[(f, sourced)][m] for m in MARKS["gap"])) for f, sourced in keys]

    def unsourced_rows(self) -> list[tuple]:
        return [(f, self.gap_labels.get(f, ""), len(ids), " ".join(ids))
                for f, ids in sorted(self.unsourced_needed.items(), key=lambda item: _order(FIELD_ORDER, item[0]))]

    def statement_rows(self) -> list[tuple]:
        ids = sorted(self.statement_marks, key=lambda s: _order(GUIDE_ORDER, s))
        return [(s, *self.statement_info[s], *(self.statement_marks[s][m] for m in MARKS["statement"]))
                for s in ids]


def _order(order: list[str], item: str) -> tuple:
    """Guide order; anything not in the guide (an older log) after it, alphabetically."""
    return (order.index(item), "") if item in order else (len(order), item)


def read_log(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_report(entries: list[dict], log_path: Path = REVIEW_LOG_PATH) -> TrialReport:
    report = TrialReport(log_path)
    for entry in entries:
        report.decisions += 1
        report.cases[entry["case_id"]] += 1
        report.log_versions[entry.get("log_version", 1)] += 1
        logged = entry.get("logged_at", "")
        report.first_logged = min(report.first_logged or logged, logged)
        report.last_logged = max(report.last_logged, logged)
        report.decision_counts[entry["decision"]] += 1
        if entry["decision"] == "edit":
            report.edit_notes.append((logged, entry["case_id"], entry.get("ui_language", "en"), entry.get("note") or ""))
        for gap in entry["gaps"]:
            sourced = gap.get("source") is not None
            mark = gap.get("reviewer_judgement")
            report.gap_marks[(gap["field"], sourced)][mark] += 1
            report.gap_labels[gap["field"]] = gap.get("label", "")
            if mark == "needed" and not sourced:
                report.unsourced_needed[gap["field"]].append(entry["case_id"])
        for part in ("components", "fitting"):  # absent before log versions 3 and 4
            for section in (entry.get(part) or {}).get("sections", []):
                for statement in section["statements"]:
                    report.statement_marks[statement["id"]][statement.get("reviewer_judgement")] += 1
                    report.statement_info[statement["id"]] = (part, section["component"], statement.get("doc_id", ""))
    return report


def write_csv(report: TrialReport, path: Path) -> None:
    """One CSV file in sections: a title row ("# ..."), a header row, the rows, a blank row."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:  # Excel shows Arabic notes with the BOM
        writer = csv.writer(f)

        def section(title, header, rows):
            writer.writerow([f"# {title}"])
            writer.writerow(header)
            writer.writerows(rows)
            writer.writerow([])

        section("Trial report (counts only)", ["item", "value"], [
            ("review log", report.log_path.as_posix()),
            ("decisions logged", report.decisions),
            ("cases", len(report.cases)),
            ("cases with more than one decision", sum(1 for n in report.cases.values() if n > 1)),
            ("first decision (UTC)", report.first_logged),
            ("last decision (UTC)", report.last_logged),
            ("log versions", " ".join(f"v{v}: {n}" for v, n in sorted(report.log_versions.items()))),
        ])
        section("Gap fields", ["field", "label", "source passage shown", "needed", "not needed", "not marked"],
                report.gap_rows())
        section("Gaps shown without a source and marked Needed",
                ["field", "label", "times", "case ids"], report.unsourced_rows())
        section("Statements", ["statement id", "part", "section", "source document", "relevant",
                               "not relevant", "not marked"], report.statement_rows())
        section("Decisions", ["decision", "count"],
                [(d, report.decision_counts[d]) for d in DECISIONS]
                + [(d, n) for d, n in sorted(report.decision_counts.items()) if d not in DECISIONS])
        section("Edit notes", ["logged at (UTC)", "case id", "page language", "note"], report.edit_notes)


def print_summary(report: TrialReport, out=sys.stdout) -> None:
    p = lambda *args: print(*args, file=out)  # noqa: E731
    repeated = sum(1 for n in report.cases.values() if n > 1)
    p(f"Review log: {report.log_path}")
    if not report.decisions:
        p("No decisions logged yet.")
        return
    p(f"{report.decisions} decisions on {len(report.cases)} cases ({repeated} cases decided more than once), "
      f"{report.first_logged} to {report.last_logged} UTC")
    p("Decisions: " + ", ".join(f"{d} {report.decision_counts[d]}" for d in DECISIONS))

    p("\nGap fields (source = a source passage was shown)")
    p(f"  {'field':34} {'source':6} {'needed':>6} {'not needed':>10} {'not marked':>10}")
    for f, _, sourced, needed, not_needed, unmarked in report.gap_rows():
        p(f"  {f:34} {sourced:6} {needed:6} {not_needed:10} {unmarked:10}")

    p("\nGaps shown without a source and marked Needed (where the library may lack a source)")
    for f, _, times, ids in report.unsourced_rows() or [("(none)", "", "", "")]:
        p(f"  {f:34} {times!s:>3}  {ids}")

    rows = report.statement_rows()
    marked = [row for row in rows if row[4] or row[5]]
    p(f"\nStatements: {len(rows)} shown, {len(marked)} marked at least once")
    p(f"  {'statement id':46} {'part':10} {'relevant':>8} {'not relevant':>12} {'not marked':>10}")
    for statement_id, part, _, _, relevant, not_relevant, unmarked in marked:
        p(f"  {statement_id:46} {part:10} {relevant:8} {not_relevant:12} {unmarked:10}")

    p(f"\nEdit notes ({len(report.edit_notes)})")
    for logged, case_id, lang, note in report.edit_notes:
        p(f"  {logged}  {case_id}  [{lang}]  {note}")


def main(argv=None) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="python -m review.trial_report", description=__doc__.splitlines()[0])
    parser.add_argument("--log", type=Path, default=REVIEW_LOG_PATH)
    parser.add_argument("--out", type=Path, default=REPORT_PATH)
    args = parser.parse_args(argv)
    report = build_report(read_log(args.log), args.log)
    print_summary(report)
    write_csv(report, args.out)
    print(f"\nWritten: {args.out}")


if __name__ == "__main__":
    main()
