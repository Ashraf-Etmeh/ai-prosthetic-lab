"""Load the prepared trial cases into the app, so the prosthetist reviews them instead of typing them.

  python -m intake.load_trial_cases              every data/trial/cases/*.json
  python -m intake.load_trial_cases FILE ...     only these files

Each file holds one fake case in the shape of Case.to_dict() (no patient
identifiers), with a fixed id that matches its file name, e.g.
trial-01.json -> "trial-01". The case is analysed exactly as a submitted
intake form is (intake/routes.py analyse_case: search, gaps, components,
fitting) and saved to data/cases/, so its review page is
http://127.0.0.1:5000/review/trial-01.

Loading again analyses the case again and replaces its saved analysis; the
review log is never touched. Run it while the app is stopped, or restart the
app afterwards: a running app keeps a case it has already shown in memory.
"""

import json
import sys
from pathlib import Path

from intake.routes import analyse_case
from shared.case_schema import Case
from shared.config import TRIAL_DIR
from shared.store import CaseRecord, store

TRIAL_CASES_DIR = TRIAL_DIR / "cases"
REVIEW_URL = "http://127.0.0.1:5000/review/{case_id}"


def read_case(path: Path) -> Case:
    """The case in a trial file. Its case_id must be the file name, so each review link is stable."""
    data = json.loads(path.read_text(encoding="utf-8"))
    case = Case.from_dict(data)
    if case.case_id != path.stem:
        raise ValueError(f"{path.name}: case_id {case.case_id!r} must match the file name ({path.stem!r})")
    return case


def load(paths: list[Path]) -> list[CaseRecord]:
    """Read every file first (a bad file stops the load before anything is saved), then analyse and save."""
    cases = [read_case(path) for path in paths]
    records = []
    for case in cases:
        record = analyse_case(case)
        store.save(record)
        records.append(record)
    return records


def describe(record: CaseRecord) -> str:
    case = record.case
    k_level = case.activity.k_level.value if case.activity.k_level else "-"
    cited = sum(1 for gap in record.gaps if gap.evidence is not None)
    return (f"{case.case_id:9} {case.amputation_level.value:25} {case.side.value:9} K: {k_level:7} "
            f"{len(record.gaps):2} gaps ({cited:2} with a source)  {REVIEW_URL.format(case_id=case.case_id)}")


def main(argv=None) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:] if argv is None else argv
    paths = [Path(arg) for arg in args] or sorted(TRIAL_CASES_DIR.glob("*.json"))
    if not paths:
        sys.exit(f"No trial cases in {TRIAL_CASES_DIR}")
    print(f"Analysing {len(paths)} trial case(s); the first one loads the search model (10-30 s) ...")
    records = load(paths)
    for record in records:
        print(describe(record))
    warnings = {record.knowledge_warning for record in records if record.knowledge_warning}
    for warning in warnings:
        print(f"WARNING {warning}")
    print(f"Saved to {store.folder}. Start (or restart) the app with: python app.py")


if __name__ == "__main__":
    main()
