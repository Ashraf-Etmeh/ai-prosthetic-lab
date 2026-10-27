"""One person's record across domains (use case 07; SYSTEM_DESIGN.md §7.4; plan Part 8, 2026-10-27).

The record holds a person code the app makes (P- and six hex digits), never a name, birth date or file number:
those stay in the clinic's own system (owner, 2026-10-27; CLAUDE.md principle 4). Each person is one file,
data/records/people/<code>.jsonl, of lines only ever added to, as clinical records keep consent and notes:

    created   the record was opened
    consent   one consent item agreed, declined or withdrawn, and the language its text was shown in; the
              latest line per item is the one that holds, earlier ones stay
    case      a case attached (at its intake, never later: the consent to the cloud model is known before
              anything is sent)
    note      a hand-over note from one team member to the next (stays here, never sent to a language model)
    request   a copy given, or a deletion requested and on whose request (the deletion itself is done by the
              owner by hand: owner, 2026-10-27)
    deleted   written by the owner when carrying out a deletion: the file then keeps only its created line, the
              request and this line (README.md, "Patient record")

What the consent does: a case attached to a person goes to the cloud model only while the person's latest
"cloud_model" line says agreed (reasoning/rag.py generate; owner, 2026-10-27), and its review-log lines are
left out of the quality counts unless "quality_use" says agreed. A case with no person (the test, golden and
teaching cases) works as before. Who recorded a line is not kept until roles and sign-in come.
"""

import json
import re
import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from shared import config
from shared.i18n import LANGUAGES, TranslatableError

RECORD_VERSION = 1
# The four consent items, each separate (SYSTEM_DESIGN.md §7.4).
CONSENT_ITEMS = ("care_record", "cloud_model", "quality_use", "teaching_use")
ANSWERS = ("agreed", "declined", "withdrawn")
REQUESTS = ("copy", "deletion")
REQUESTED_BY = ("person", "representative", "clinic")
MAX_NOTE = 2000  # characters in one hand-over note
CODE = re.compile(r"P-[0-9A-F]{6}")
# Why a case went without the AI (reasoning/rag.py; shown on the review page, in English like the other reasons).
CONSENT_OFF = ("the person's consent to send coded fields to the cloud model is not recorded as agreed "
               "(patient record, consent)")
_write_lock = threading.Lock()


class PersonError(TranslatableError):
    """A change to a person's record that is refused, with a message for the page."""


@dataclass(frozen=True)
class ConsentLine:
    item: str
    answer: str
    language: str  # the language the consent text was shown in
    at: str


@dataclass(frozen=True)
class CaseLink:
    case_id: str
    domain: str
    at: str


@dataclass(frozen=True)
class Note:
    text: str
    at: str


@dataclass(frozen=True)
class Request:
    kind: str
    by: Optional[str]  # deletion: on whose request; a copy: None
    at: str


@dataclass
class Person:
    code: str
    created_at: str
    consent: list[ConsentLine] = field(default_factory=list)
    cases: list[CaseLink] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)
    requests: list[Request] = field(default_factory=list)
    deleted_at: Optional[str] = None  # the owner carried out a deletion: the content is gone, this line stays

    def consent_now(self, item: str) -> Optional[ConsentLine]:
        """The line that holds for the item: its latest (None: never recorded)."""
        return next((line for line in reversed(self.consent) if line.item == item), None)

    def agrees(self, item: str) -> bool:
        line = self.consent_now(item)
        return line is not None and line.answer == "agreed"

    @property
    def deletion_requested(self) -> Optional[Request]:
        return next((r for r in reversed(self.requests) if r.kind == "deletion"), None)

    def case_ids(self) -> list[str]:
        return [link.case_id for link in self.cases]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _path(code: str) -> Path:
    return config.PEOPLE_DIR / f"{code}.jsonl"


def _append(code: str, kind: str, **values) -> dict:
    line = {"record_version": RECORD_VERSION, "kind": kind, "at": _now(), **values}
    path = _path(code)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _write_lock, path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    return line


def _lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def person_from_lines(code: str, lines: list[dict]) -> Person:
    """The record as its lines say, in order (a line of a kind this version does not know is skipped)."""
    person = Person(code, lines[0]["at"] if lines else "")
    for line in lines:
        kind, at = line.get("kind"), line.get("at", "")
        if kind == "consent":
            person.consent.append(ConsentLine(line["item"], line["answer"], line["language"], at))
        elif kind == "case":
            person.cases.append(CaseLink(line["case_id"], line["domain"], at))
        elif kind == "note":
            person.notes.append(Note(line["text"], at))
        elif kind == "request":
            person.requests.append(Request(line["request"], line.get("by"), at))
        elif kind == "deleted":
            person.deleted_at = at
    return person


def get_person(code: str) -> Optional[Person]:
    if not CODE.fullmatch(code or ""):
        return None
    path = _path(code)
    return person_from_lines(code, _lines(path)) if path.is_file() else None


def all_people() -> list[Person]:
    folder = config.PEOPLE_DIR
    paths = sorted(folder.glob("P-*.jsonl")) if folder.is_dir() else []
    return [person_from_lines(p.stem, _lines(p)) for p in paths if CODE.fullmatch(p.stem)]


def new_person() -> Person:
    """A new record under a code no other record has."""
    while True:
        code = f"P-{secrets.token_hex(3).upper()}"
        if not _path(code).exists():
            break
    _append(code, "created")
    return get_person(code)


def record_consent(person: Person, item: str, answer: str, language: str) -> ConsentLine:
    """Add a consent line. Withdrawing needs an agreement to withdraw; the same answer twice is refused."""
    if item not in CONSENT_ITEMS or answer not in ANSWERS or language not in LANGUAGES:
        raise PersonError("error.invalid_input")
    now = person.consent_now(item)
    if answer == "withdrawn" and not person.agrees(item):
        raise PersonError("error.consent_withdraw_unagreed")
    if now is not None and now.answer == answer:
        raise PersonError("error.consent_same")
    line = _append(person.code, "consent", item=item, answer=answer, language=language)
    return ConsentLine(item, answer, language, line["at"])


def person_of(case_id: str) -> Optional[Person]:
    """The person a case is attached to, or None."""
    return next((p for p in all_people() if case_id in p.case_ids()), None)


def person_for_intake(raw: Optional[str]) -> Optional[Person]:
    """The person a new case will be attached to, from the intake's "person code" field (empty: none)."""
    code = (raw or "").strip().upper()
    if not code:
        return None
    person = get_person(code)
    if person is None:
        raise PersonError("error.person_unknown", code=code[:12])
    if not person.agrees("care_record"):
        raise PersonError("error.person_no_care_record", code=code)
    if person.deletion_requested:
        raise PersonError("error.person_deletion_open", code=code)
    return person


def attach_case(person: Person, case) -> None:
    """Attach a case at its intake, before it is analysed (so the cloud consent applies to it)."""
    if not person.agrees("care_record"):
        raise PersonError("error.person_no_care_record", code=person.code)
    if person_of(case.case_id) is None:
        _append(person.code, "case", case_id=case.case_id, domain=case.domain)


def add_note(person: Person, text: Optional[str]) -> Note:
    text = (text or "").strip()
    if not text:
        raise PersonError("error.note_empty")
    if len(text) > MAX_NOTE:
        raise PersonError("error.note_too_long", n=MAX_NOTE)
    line = _append(person.code, "note", text=text)
    return Note(text, line["at"])


def record_request(person: Person, kind: str, by: Optional[str] = None) -> Request:
    if kind not in REQUESTS or (kind == "deletion" and by not in REQUESTED_BY):
        raise PersonError("error.invalid_input")
    line = _append(person.code, "request", request=kind, by=by if kind == "deletion" else None)
    return Request(kind, line["by"], line["at"])


# ---- What the consent does --------------------------------------------------------------


def cloud_consent(case_id: str) -> Optional[bool]:
    """None: the case has no person (it works as before); else whether its person agreed to the cloud model."""
    person = person_of(case_id)
    return None if person is None else person.agrees("cloud_model")


def counts_allowed(case_id: str) -> bool:
    """Whether a case's review-log lines may be counted in the quality measures: no person, or one who agreed."""
    person = person_of(case_id)
    return person is None or person.agrees("quality_use")


def left_out_of_counts() -> set[str]:
    """The case ids whose review-log lines the quality measures leave out (their person did not agree)."""
    return {case_id for person in all_people() if not person.agrees("quality_use") for case_id in person.case_ids()}
