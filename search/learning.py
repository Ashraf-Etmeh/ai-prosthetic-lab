"""Case-based learning (use case 06; SYSTEM_DESIGN.md §7.3; docs/design/08-search-and-education/Learning.html; plan
Part 7, 2026-10-25).

Teaching cases (data/education/teaching_cases/<id>.json, the educator's; the yardstick hook asks before Claude
edits them) are invented, never copied from records. Each holds a fake case (a domain's case, read with
shared/case_schema.py case_from_dict), and what only the educator sets: its status (draft or approved), its level,
the CPD time it is worth, and the expert panel's answers, recorded once and versioned (each a new version, never
an edit): which pieces of information the panel members marked as missing, and their reasoning in their own
words. Until the owner decides who sits on the panel (SYSTEM_DESIGN.md §11.9) the panel has no answers, and the
pages say so.

A learner works a case in five steps (read it; mark what is missing; write the options they would weigh and why;
compare with the panel and with what the sources say; reflect and log). Each attempt is kept on this machine
while in progress (data/records/learning/attempts/); a finished one is added to the learning log
(data/records/learning/log.jsonl), one line per case worked, never edited. One log for this machine until roles
and login come (owner, 2026-10-25). The tool never grades clinical judgement: it shows where the learner and the
panel differ.
"""

import csv
import io
import json
import re
import secrets
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from shared import config, domains
from shared.case_schema import CaseCore, case_from_dict
from shared.dates import DateError, check_date

TEACHING_CASE_VERSION = 1
STATUSES = ("draft", "approved")
LEVELS = ("foundation", "intermediate", "advanced")
STEPS = ("read", "missing", "options", "compare", "reflect")
MAX_TEXT = 1500  # characters in one of the learner's texts
MAX_MINUTES = 600
_ID = re.compile(r"[A-Za-z0-9_-]{1,32}")
_ATTEMPT = re.compile(r"[0-9a-f]{12}")
_write_lock = threading.Lock()


class TeachingCaseError(ValueError):
    """A teaching case file that can't be used as it is."""


@dataclass(frozen=True)
class PanelVersion:
    """The expert panel's answers, as the educator recorded them once."""

    version: int
    recorded_on: str  # YYYY-MM-DD
    members: int  # how many answered
    missing: dict[str, int]  # field path -> how many members marked it missing
    reasoning: tuple[str, ...]  # each member's reasoning, in their own words


@dataclass(frozen=True)
class TeachingCase:
    id: str
    status: str
    level: Optional[str]  # set by the educator; None: not set yet
    minutes: Optional[int]  # the CPD time the educator sets; None: not set yet
    case: CaseCore
    panel: tuple[PanelVersion, ...] = ()
    note: Optional[str] = None  # e.g. who drafted it and what awaits the educator

    @property
    def domain(self) -> str:
        return self.case.domain

    @property
    def panel_now(self) -> Optional[PanelVersion]:
        return self.panel[-1] if self.panel else None


def _field_paths(domain: str) -> set[str]:
    return {info.path for info in domains.part(domain, "fields").FIELDS}


def teaching_case_from_dict(data: dict, file_stem: Optional[str] = None) -> TeachingCase:
    """A teaching case, checked; TeachingCaseError if it is not valid."""
    where = data.get("id") or file_stem or "?"
    if data.get("teaching_case_version") != TEACHING_CASE_VERSION:
        raise TeachingCaseError(f"{where}: teaching_case_version must be {TEACHING_CASE_VERSION}")
    if not _ID.fullmatch(str(data.get("id", ""))) or (file_stem and data["id"] != file_stem):
        raise TeachingCaseError(f"{where}: the id must be letters, digits, - or _, and the file's name")
    if data.get("status") not in STATUSES:
        raise TeachingCaseError(f"{where}: status must be one of {STATUSES}")
    if data.get("level") is not None and data["level"] not in LEVELS:
        raise TeachingCaseError(f"{where}: level must be one of {LEVELS} or null")
    minutes = data.get("minutes")
    if minutes is not None and (not isinstance(minutes, int) or not 0 < minutes <= MAX_MINUTES):
        raise TeachingCaseError(f"{where}: minutes must be a whole number from 1 to {MAX_MINUTES}, or null")
    try:
        case = case_from_dict(dict(data["case"]))
    except (KeyError, TypeError, ValueError) as error:
        raise TeachingCaseError(f"{where}: the case can't be read: {error}") from None
    paths = _field_paths(case.domain)
    panel = []
    for number, raw in enumerate(data.get("panel") or [], start=1):
        try:
            version = PanelVersion(int(raw["version"]), check_date(raw["recorded_on"]), int(raw["members"]),
                                   {str(k): int(v) for k, v in raw["missing"].items()},
                                   tuple(str(r) for r in raw.get("reasoning") or ()))
        except (KeyError, TypeError, ValueError, DateError) as error:
            raise TeachingCaseError(f"{where}: panel version {number} can't be read: {error}") from None
        if version.version != number or version.members < 1 or set(version.missing) - paths \
                or any(not 0 <= n <= version.members for n in version.missing.values()):
            raise TeachingCaseError(f"{where}: panel version {number}: versions are numbered from 1, members "
                                    f"from 1, and each missing item is a field of the case with at most "
                                    f"{version.members} members")
        panel.append(version)
    return TeachingCase(data["id"], data["status"], data.get("level"), minutes, case, tuple(panel), data.get("note"))


def load_teaching_cases(folder: Optional[Path] = None) -> list[TeachingCase]:
    """Every teaching case, by id (TeachingCaseError if one is not valid)."""
    folder = folder or config.TEACHING_CASES_DIR
    cases = []
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        cases.append(teaching_case_from_dict(json.loads(path.read_text(encoding="utf-8")), path.stem))
    return cases


def teaching_case(case_id: str, folder: Optional[Path] = None) -> Optional[TeachingCase]:
    return next((c for c in load_teaching_cases(folder) if c.id == case_id), None)


# ---- A learner's attempt -------------------------------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Attempt:
    id: str
    case_id: str
    started_at: str
    missing: list[str] = field(default_factory=list)  # field paths the learner marked as missing
    other_missing: Optional[str] = None  # anything else they would want, in their words
    options: Optional[str] = None  # the options they would weigh
    reasons: Optional[str] = None  # and why
    reflection: Optional[str] = None  # kept in the learning log only
    minutes: Optional[int] = None  # the time they spent, as they record it
    done: list[str] = field(default_factory=list)  # the steps done

    def step_done(self, step: str) -> bool:
        return step in self.done


def _attempts_dir() -> Path:
    return config.LEARNING_DIR / "attempts"


def start_attempt(case_id: str) -> Attempt:
    attempt = Attempt(secrets.token_hex(6), case_id, _now(), done=["read"])
    save_attempt(attempt)
    return attempt


def save_attempt(attempt: Attempt) -> None:
    folder = _attempts_dir()
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{attempt.id}.json").write_text(json.dumps(asdict(attempt), ensure_ascii=False, indent=1),
                                               encoding="utf-8")


def get_attempt(attempt_id: str) -> Optional[Attempt]:
    if not _ATTEMPT.fullmatch(attempt_id or ""):
        return None
    path = _attempts_dir() / f"{attempt_id}.json"
    return Attempt(**json.loads(path.read_text(encoding="utf-8"))) if path.is_file() else None


# ---- The learning log ----------------------------------------------------------------


def _log_path() -> Path:
    return config.LEARNING_DIR / "log.jsonl"


def log_attempt(attempt: Attempt, case: TeachingCase) -> dict:
    """Add the finished attempt to the learning log, with what was shown: the case's status and level and the
    panel version it was compared with."""
    panel = case.panel_now
    entry = {"logged_at": _now(), "attempt": asdict(attempt), "case_id": case.id, "domain": case.domain,
             "case_status": case.status, "level": case.level, "summary": case_summary_key(case),
             "panel_version": panel.version if panel else None}
    path = _log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _write_lock, path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def read_log() -> list[dict]:
    path = _log_path()
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def case_summary_key(case: TeachingCase) -> str:
    """What the log groups cases by: an amputation level, or a domain's own group (e.g. the condition)."""
    value = getattr(case.case, "amputation_level", None) or getattr(case.case, "condition", None)
    return getattr(value, "value", None) or case.domain


def log_summary(entries: list[dict]) -> dict:
    """{"cases": n, "minutes": total the learner recorded, "groups": {summary key: n}}: counts only."""
    groups: dict[str, int] = {}
    for entry in entries:
        groups[entry["summary"]] = groups.get(entry["summary"], 0) + 1
    return {"cases": len(entries), "minutes": sum(entry["attempt"].get("minutes") or 0 for entry in entries),
            "groups": groups}


CPD_COLUMNS = ("date (UTC)", "teaching case", "domain", "level set by the educator", "minutes recorded",
               "reflection")


def cpd_csv(entries: list[dict]) -> str:
    """The CPD record: one row per case worked, as logged (UTF-8 with BOM so a spreadsheet shows Arabic)."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(CPD_COLUMNS)
    for entry in entries:
        writer.writerow([entry["logged_at"][:10], entry["case_id"], entry["domain"], entry["level"] or "",
                         entry["attempt"].get("minutes") or "", entry["attempt"].get("reflection") or ""])
    return "﻿" + out.getvalue()
