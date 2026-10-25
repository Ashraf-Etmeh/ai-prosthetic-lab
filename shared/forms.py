"""What every form shares: reading a submitted value, refused in the form's own words.

Each parser refuses a value with the form's own label for the field (a
shared/i18n.py key), never with Python's wording. Used by each domain's intake
(prosthetics/intake.py, orthotics/intake.py) and module pages (prosthetics/modules.py,
orthotics/modules.py): the module pages' typed values, tables, requirements and
follow-up are read here once for every domain (SYSTEM_DESIGN.md §5).
"""

import math
from typing import Optional

from shared.dates import DateError, check_date
from shared.followup import Alert, FollowUp, MeasureDef, Visit, VisitStatus
from shared.i18n import TextKey, TranslatableError
from shared.requirements import Conflict, Priority, Requirement

MAX_PRIOR_DEVICES = 3  # device rows on the form
# The module pages' limits.
MAX_TEXT = 500  # characters in one typed value (a requirement, a note, a parameter)
MAX_LONG_TEXT = 3000  # characters in a long text (a patient leaflet)
MAX_LIST = 8  # lines in a typed list (costs, checks at fitting)
MAX_ROWS = 20  # rows in one table (visits, tuning, observations)
MAX_REQUIREMENTS = 30
NEW_ROWS = 3  # empty rows offered for adding
# Typed alone in the comorbidities box: asked, none reported. The Arabic
# form tells the user to type لا يوجد.
NONE_ANSWERS = ("none", "لا يوجد", "لا شيء")


def required(form, name: str) -> str:
    # form[name] would raise KeyError, which Flask's debug mode shows as a
    # crash page (500) instead of the form with a message.
    value = form.get(name)
    if not value:
        raise TranslatableError(f"error.required.{name}")
    return value


# Each parser below refuses a value with the form's own label for the field
# (a shared/i18n.py key), never with Python's wording.

def choice(enum_cls, raw: str, label: str):
    try:
        return enum_cls(raw)
    except ValueError:
        raise TranslatableError("error.unknown_choice", field=TextKey(label)) from None


def optional_enum(enum_cls, raw: str | None, label: str):
    if not raw:
        return None
    return choice(enum_cls, raw, label)


def optional_number(raw: str | None, label: str, whole: bool = False, positive: bool = False):
    """The number typed, or None if left empty. 0 or more; greater than 0 if `positive`."""
    if not raw or not raw.strip():
        return None
    try:
        value = int(raw) if whole else float(raw)
    except ValueError:
        raise TranslatableError("error.whole_number" if whole else "error.number",
                                field=TextKey(label)) from None
    if not math.isfinite(value):  # "nan", "inf"
        raise TranslatableError("error.number", field=TextKey(label))
    if positive and value <= 0:
        raise TranslatableError("error.positive", field=TextKey(label))
    if value < 0:
        raise TranslatableError("error.not_negative", field=TextKey(label))
    return value


def optional_list(raw: str | None) -> list[str] | None:
    # One item per line. Blank -> None (not recorded); "none" -> [] (asked, none reported).
    items = [line.strip() for line in (raw or "").splitlines() if line.strip()]
    if not items:
        return None
    if len(items) == 1 and items[0].lower() in NONE_ANSWERS:
        return []
    return items


def optional_bool(raw: str | None) -> bool | None:
    if not raw:
        return None
    if raw not in ("yes", "no"):
        raise TranslatableError("error.yes_no", value=raw)
    return raw == "yes"


# ---- The module pages (every domain's) ----------------------------------------------


def text(raw: Optional[str], label: str, **params) -> Optional[str]:
    """A typed value, stripped; None if left empty. Longer than MAX_TEXT is refused."""
    value = (raw or "").strip() or None
    if value is not None and len(value) > MAX_TEXT:
        raise TranslatableError("error.too_long", field=TextKey(label), n=MAX_TEXT, **params)
    return value


def long_text(raw: Optional[str], label: str) -> Optional[str]:
    value = (raw or "").strip() or None
    if value is not None and len(value) > MAX_LONG_TEXT:
        raise TranslatableError("error.too_long", field=TextKey(label), n=MAX_LONG_TEXT)
    return value


def lines(raw: Optional[str], label: str, limit: int = MAX_LIST) -> list[str]:
    """A typed list, one item per line (empty lines left out)."""
    items = [line.strip() for line in (raw or "").splitlines() if line.strip()]
    for item in items:
        text(item, label)
    if len(items) > limit:
        raise TranslatableError("error.too_many_lines", field=TextKey(label), n=limit)
    return items


def member(cls, raw: Optional[str]):
    """The vocabulary member a form sent, None if left empty; a value not offered is refused."""
    if not raw:
        return None
    try:
        return cls(raw)
    except ValueError:
        raise TranslatableError("error.invalid_input") from None


def date(raw: Optional[str], label: str) -> Optional[str]:
    try:
        return check_date((raw or "").strip() or None)
    except DateError:
        raise TranslatableError("error.date", field=TextKey(label)) from None


def count(form, name: str, limit: int) -> int:
    """How many rows a table form sent (at most `limit` plus the empty rows offered)."""
    try:
        return min(int(form.get(name, "0")), limit + NEW_ROWS)
    except ValueError:
        raise TranslatableError("error.invalid_input") from None


def rows(form, prefix: str, columns: tuple[str, ...], label: str, limit: int = MAX_ROWS,
         flags: tuple[str, ...] = ()) -> list[dict]:
    """A table form's rows ('<prefix>_<n>_<column>'); a row whose text columns are all empty is left out."""
    kept = []
    for n in range(1, count(form, f"{prefix}_rows", limit) + 1):
        row = {column: text(form.get(f"{prefix}_{n}_{column}"), label) for column in columns}
        if not any(row.values()):
            continue
        row.update({flag: bool(form.get(f"{prefix}_{n}_{flag}")) for flag in flags})
        kept.append(row)
    if len(kept) > limit:
        raise TranslatableError("error.too_many_rows", field=TextKey(label), n=limit)
    return kept


def requirements_from_form(form, existing: list[Requirement], known: set[str]) -> list[Requirement]:
    """The requirements table ('rows', 'req_<n>_id|text|finding|priority'). An emptied row removes its
    requirement; a new row gets the next free id. `known`: the finding keys a requirement may name."""
    existing_ids = {r.id for r in existing}
    kept, numbers = [], [int(i[1:]) for i in existing_ids if i[1:].isdigit()]
    next_number = max(numbers, default=0) + 1
    for n in range(1, count(form, "rows", MAX_REQUIREMENTS) + 1):
        typed = text(form.get(f"req_{n}_text"), "req.requirement")
        if typed is None:
            continue  # an emptied row removes its requirement
        requirement_id = form.get(f"req_{n}_id") or ""
        if requirement_id not in existing_ids:
            requirement_id, next_number = f"R{next_number}", next_number + 1
        findings = form.getlist(f"req_{n}_finding")
        if set(findings) - known:
            raise TranslatableError("error.invalid_input")
        kept.append(Requirement(requirement_id, typed, findings, member(Priority, form.get(f"req_{n}_priority"))))
    if len(kept) > MAX_REQUIREMENTS:
        raise TranslatableError("error.too_many_requirements", n=MAX_REQUIREMENTS)
    return kept


def conflicts_from_form(form, note_label: str = "req.conflict_note") -> list[Conflict]:
    """The conflicts' rows; `note_label`: the note's label in the domain's words (for a refusal)."""
    conflicts = []
    for row in rows(form, "conflict", ("first", "second", "note"), note_label):
        if not (row["first"] and row["second"] and row["note"]):
            raise TranslatableError("error.conflict_incomplete")
        conflicts.append(Conflict(row["first"], row["second"], row["note"]))
    return conflicts


def _visits_from_form(form, follow_up: FollowUp) -> list[Visit]:
    visits = []
    names = [m.name for m in follow_up.measures]
    for n in range(1, count(form, "visit_rows", MAX_ROWS) + 1):
        prefix = f"visit_{n}_"
        name = text(form.get(prefix + "name"), "fu.visit")
        values = {}
        for k, measure in enumerate(names, 1):
            value = text(form.get(f"{prefix}value_{k}"), "fu.value")
            if value:
                values[measure] = value
        texts = {key: text(form.get(prefix + key), f"fu.{key}") for key in
                 ("wearing", "puts_on_alone", "device_condition", "notes")}
        if name is None:
            if values or any(texts.values()) or form.get(prefix + "date"):
                raise TranslatableError("error.visit_needs_name")
            continue
        visits.append(Visit(name, date(form.get(prefix + "date"), "fu.date"),
                            member(VisitStatus, form.get(prefix + "status")) or VisitStatus.NOT_BOOKED, values,
                            **texts))
    if len(visits) > MAX_ROWS:
        raise TranslatableError("error.too_many_rows", field=TextKey("fu.visits"), n=MAX_ROWS)
    return visits


def follow_up_from_form(form, follow: FollowUp, back_to: tuple[str, ...]) -> None:
    """One of the follow-up page's forms (action "measures", "visits" or "alerts") into `follow`.
    `back_to`: the modules the domain lets an alert loop back to. Refused before anything changes."""
    action = form.get("action")
    if action == "measures":
        table = rows(form, "measure", ("name", "unit", "how"), "fu.measures", MAX_LIST)
        if any(not r["name"] for r in table):
            raise TranslatableError("error.measure_needs_name")
        renamed = {old.name for old in follow.measures} - {r["name"] for r in table}
        due_next = text(form.get("due_next"), "fu.due_next")
        follow.measures = [MeasureDef(r["name"], r["unit"], r["how"]) for r in table]
        for visit in follow.visits:  # a measure taken out takes its values with it
            visit.values = {k: v for k, v in visit.values.items() if k not in renamed}
        follow.due_next = due_next
    elif action == "visits":
        follow.visits = _visits_from_form(form, follow)
    elif action == "alerts":
        alerts = []
        for r in rows(form, "alert", ("text", "back_to"), "fu.alerts", MAX_LIST, flags=("resolved",)):
            if not r["text"]:
                raise TranslatableError("error.alert_needs_text")
            if r["back_to"] and r["back_to"] not in back_to:
                raise TranslatableError("error.invalid_input")
            alerts.append(Alert(r["text"], r["back_to"], r["resolved"]))
        follow.alerts = alerts
    else:
        raise TranslatableError("error.invalid_input")
