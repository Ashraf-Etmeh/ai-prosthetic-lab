"""What the quality page measures (SYSTEM_DESIGN.md §7.2, "Quality and audit"; plan Part 4, 2026-10-25).

Counts only, never what a record says: the share of the AI's sentences the
quote check removed (from the case files on this machine), the share of
reviewers' "summary is wrong" marks (from the review log), the release gate
(from the recorded results, quality/results.py, and the owner's sign-offs,
quality/releases.py) and the audit trail (who did what, when, with which
versions). Each function takes what it reads, so a test can hand it records.

"Who" is not recorded yet: the app has no login (roles come with the patient
record, plan Part 8; owner's answer, 2026-10-25).
"""

from typing import Iterable, Optional

from quality import results
from quality.releases import Release

DESIGN_CHOICE = "design_choice"  # review/decision_log.py: a choice on a module page, nothing marked
FIRST_WRONG_MARK = 11  # the review log version that added "summary_wrong"
AUDIT_ROWS = 25


def quote_check_counts(case_files: Iterable[dict]) -> dict:
    """{"cases", "kept", "removed"}: the AI's items kept, and those the quote check took out (a quote shown
    under an earlier topic is not counted: it was not a failed check), over case files with an AI answer."""
    cases = kept = removed = 0
    for data in case_files:
        generation = data.get("generation")
        if not generation:
            continue
        cases += 1
        for part in generation.get("parts", {}).values():
            kept += len(part.get("items") or [])
            removed += sum(1 for entry in part.get("removed") or [] if entry.get("dropped") == "item")
    return {"cases": cases, "kept": kept, "removed": removed}


def summary_wrong_counts(entries: Iterable[dict]) -> dict:
    """{"decisions", "marked", "wrong"}: the statements reviewers marked, and those marked "summary is wrong",
    in the decisions logged since the mark existed (log version 11)."""
    decisions = marked = wrong = 0
    for entry in entries:
        if entry.get("decision") == DESIGN_CHOICE or entry.get("log_version", 1) < FIRST_WRONG_MARK:
            continue
        decisions += 1
        for part in ("components", "fitting"):
            for section in (entry.get(part) or {}).get("sections", []):
                for statement in section["statements"]:
                    mark = statement.get("reviewer_judgement")
                    marked += mark is not None
                    wrong += mark == "summary_wrong"
    return {"decisions": decisions, "marked": marked, "wrong": wrong}


def share(part: int, whole: int) -> Optional[int]:
    """part of whole as a whole percentage; None when there is nothing to count."""
    return round(100 * part / whole) if whole else None


def release_gate(runs: list[dict], release: Optional[Release]) -> dict:
    """The gate's four conditions, as recorded: {"tests", "held_out", "arabic", "sign_off"}, each
    {"state": "pass" | "fail" | "not_recorded" | "awaiting", ...what it was read from}."""
    check = results.latest(runs, results.RELEASE_CHECK)
    tests = {"state": "not_recorded"}
    if check and check.get("unit_tests"):
        unit = check["unit_tests"]
        tests = {"state": "pass" if unit.get("ok") else "fail", "ran": unit.get("ran"), "at": check["recorded_at"]}
    held = results.latest(runs, results.GOLDEN_CASES, set=results.HELD_OUT)
    held_out = ({"state": "pass" if held["passed"] == held["cases"] else "fail", "passed": held["passed"],
                 "cases": held["cases"], "at": held["recorded_at"]} if held else {"state": "not_recorded"})
    arabic = ({"state": "pass", "by": release.arabic_checked_by, "on": release.arabic_checked_on}
              if release and release.arabic_checked else {"state": "not_recorded"})
    sign_off = ({"state": "pass", "by": release.signed_off_by, "on": release.signed_on, "release": release.release}
                if release and release.signed_off else {"state": "awaiting"})
    return {"tests": tests, "held_out": held_out, "arabic": arabic, "sign_off": sign_off}


def audit_rows(entries: list[dict], runs: list[dict], library: Optional[dict], rules: list,
               releases: list[Release], limit: int = AUDIT_ROWS) -> list[dict]:
    """The latest events, newest first: {"when", "what" (an interface text key under "audit."), "params",
    "versions" (prompt, library) where known}. Who did it is not recorded yet (no login)."""
    rows = []
    for entry in entries:
        versions = entry.get("versions") or {}
        prompt = versions.get("prompt") or (entry.get("generation") or {}).get("prompt_version")
        built = (versions.get("library") or {}).get("built")
        what = "design_choice" if entry["decision"] == DESIGN_CHOICE else "decision"
        rows.append({"when": entry["logged_at"], "what": what,
                     "params": {"decision": entry["decision"], "case": entry["case_id"],
                                "domain": entry.get("domain", "")},
                     "versions": {"prompt": prompt, "library": built}})
    for run in runs:
        built = ((run.get("versions") or {}).get("library") or {}).get("built")
        prompts = ", ".join(sorted(set(((run.get("versions") or {}).get("prompts") or {}).values())))
        if run["kind"] == results.RELEASE_CHECK:
            failed = [name for name, outcome in (run.get("steps") or {}).items() if outcome != "OK"]
            rows.append({"when": run["recorded_at"], "what": "release_check_failed" if failed else "release_check",
                         "params": {"failed": ", ".join(failed)}, "versions": {"prompt": prompts, "library": built}})
        else:
            rows.append({"when": run["recorded_at"], "what": "golden_" + run["set"],
                         "params": {"passed": run["passed"], "cases": run["cases"], "mode": run["mode"]},
                         "versions": {"prompt": prompts, "library": built}})
    if library and library.get("built"):
        rows.append({"when": library["built"], "what": "library", "params": {"n": library.get("passages")},
                     "versions": {"prompt": None, "library": library["built"]}})
    for rule in rules:
        if rule.approved:
            rows.append({"when": rule.approved_on, "what": "rule_approved",
                         "params": {"rule": rule.rule_id, "version": rule.version}, "versions": {}})
    for release in releases:
        if release.arabic_checked:
            rows.append({"when": release.arabic_checked_on, "what": "arabic_checked",
                         "params": {"release": release.release}, "versions": {}})
        if release.signed_off:
            rows.append({"when": release.signed_on, "what": "signed_off", "params": {"release": release.release},
                         "versions": {}})
    rows.sort(key=lambda row: row["when"], reverse=True)
    return rows[:limit]
