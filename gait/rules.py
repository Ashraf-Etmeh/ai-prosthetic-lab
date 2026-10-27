"""What a gait session's numbers are shown against (SYSTEM_DESIGN.md §6.3; plan Part 10, 2026-10-27).

Two of the owner's files (protected by the yardstick hook; code never writes them):
- data/knowledge/gait_thresholds.csv: the thresholds that make an indicator (a measured value past a threshold, for
  the specialist to review), each with its status like a clinic rule (data/knowledge/clinic_rules.csv): a draft is
  shown as a draft. The rows there now are Claude's drafts for the prototype (2026-10-27), awaiting the owner.
- data/knowledge/gait_references.csv: each measure's reference band and smallest real change, each copied from a
  catalogued source with its page and the source's own words (checked word for word by gait/tests). Empty until the
  owner adds them; the pages say "not set".

Code compares numbers and nothing else: an indicator says which value is past which threshold, never a cause, a
diagnosis, a fall risk or an adjustment. A comparison shows each measure's difference, and against the smallest
real change only where the owner set one from a source.
"""

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from gait.session import MEASURES, SIDES, Session
from shared import config
from shared.dates import DateError, check_date

DRAFT, APPROVED = "draft", "approved"
STATUSES = (DRAFT, APPROVED)
TESTS = ("side_difference", "side_difference_percent", "below", "above", "min_steps")
THRESHOLD_COLUMNS = ("id", "measure", "test", "value", "unit", "status", "version", "owner", "approved_on", "note")
REFERENCE_COLUMNS = ("measure", "side", "low", "high", "smallest_real_change", "unit", "doc_id", "page", "quote",
                     "status", "owner", "approved_on")
REFERENCE_SIDES = ("left", "right", "both", "any")


@dataclass(frozen=True)
class Threshold:
    id: str
    measure: str  # a gait/session.py MEASURES key, or "steps" for min_steps
    test: str
    value: float
    unit: str
    status: str
    version: int
    owner: str
    approved_on: str
    note: str

    @property
    def approved(self) -> bool:
        return self.status == APPROVED


@dataclass(frozen=True)
class Reference:
    measure: str
    side: str
    low: Optional[float]
    high: Optional[float]
    smallest_real_change: Optional[float]
    unit: str
    doc_id: str
    page: int
    quote: str
    status: str
    owner: str
    approved_on: str


def _rows(path: Path, columns: tuple[str, ...]) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if tuple(reader.fieldnames or ()) != columns:
            raise ValueError(f"{path.name}: the columns must be {', '.join(columns)}")
        return [{k: (v or "").strip() for k, v in row.items()} for row in reader]


def _status(where: str, status: str, owner: str, approved_on: str) -> None:
    if status not in STATUSES:
        raise ValueError(f"{where}: status must be one of {list(STATUSES)}")
    if status == APPROVED:
        if not owner:
            raise ValueError(f"{where}: an approved row names its owner")
        try:
            check_date(approved_on)
        except DateError:
            raise ValueError(f"{where}: approved_on must be a date (YYYY-MM-DD)") from None
    elif approved_on:
        raise ValueError(f"{where}: a draft has no approved_on")


def _float(raw: str, where: str) -> Optional[float]:
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        raise ValueError(f"{where}: not a number: {raw!r}") from None


def load_thresholds(path: Optional[Path] = None) -> list[Threshold]:
    """The owner's thresholds, each checked (ValueError if one is not valid)."""
    found = []
    for raw in _rows(path or config.GAIT_THRESHOLDS_PATH, THRESHOLD_COLUMNS):
        where = f"gait thresholds, {raw['id']}"
        if raw["test"] not in TESTS:
            raise ValueError(f"{where}: test must be one of {list(TESTS)}")
        if raw["test"] == "min_steps" and raw["measure"] != "steps":
            raise ValueError(f"{where}: min_steps is about steps")
        if raw["test"] != "min_steps" and raw["measure"] not in MEASURES:
            raise ValueError(f"{where}: unknown measure {raw['measure']!r}")
        sided = raw["test"] in ("side_difference", "side_difference_percent")
        if raw["test"] != "min_steps" and sided != MEASURES[raw["measure"]][1]:
            raise ValueError(f"{where}: a side test is for a measure per side, below and above for the others")
        value = _float(raw["value"], where)
        if value is None:
            raise ValueError(f"{where}: a threshold has its value")
        _status(where, raw["status"], raw["owner"], raw["approved_on"])
        if not raw["version"].isdigit() or int(raw["version"]) < 1:
            raise ValueError(f"{where}: version must be a whole number from 1")
        found.append(Threshold(raw["id"], raw["measure"], raw["test"], value, raw["unit"], raw["status"],
                               int(raw["version"]), raw["owner"], raw["approved_on"], raw["note"]))
    if len({t.id for t in found}) != len(found):
        raise ValueError("gait thresholds: an id is listed twice")
    return found


def load_references(path: Optional[Path] = None) -> list[Reference]:
    """The owner's reference bands and smallest real changes, each with its source's page and words."""
    found = []
    for raw in _rows(path or config.GAIT_REFERENCES_PATH, REFERENCE_COLUMNS):
        where = f"gait references, {raw['measure']}"
        if raw["measure"] not in MEASURES or raw["side"] not in REFERENCE_SIDES:
            raise ValueError(f"{where}: unknown measure or side")
        if not (raw["doc_id"] and raw["page"].isdigit() and raw["quote"]):
            raise ValueError(f"{where}: a reference names its source, page and the source's own words")
        _status(where, raw["status"], raw["owner"], raw["approved_on"])
        found.append(Reference(raw["measure"], raw["side"], _float(raw["low"], where), _float(raw["high"], where),
                               _float(raw["smallest_real_change"], where), raw["unit"], raw["doc_id"],
                               int(raw["page"]), raw["quote"], raw["status"], raw["owner"], raw["approved_on"]))
    return found


def reference_for(references: list[Reference], measure: str, side: str) -> Optional[Reference]:
    return next((r for r in references if r.measure == measure and r.side in (side, "any")), None)


# ---- Indicators ------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Indicator:
    """A measured value past a threshold (or outside a reference band), for the specialist to review."""

    id: str  # the threshold's id, or "band:<measure>:<side>"
    measure: str
    observed: dict[str, float]  # side ("left", "right" or "both") -> value
    difference: Optional[float]  # between the sides (points or %), for a side test
    threshold: Optional[Threshold] = None
    reference: Optional[Reference] = None


def _past(threshold: Threshold, session: Session) -> Optional[Indicator]:
    test, measure = threshold.test, threshold.measure
    if test in ("side_difference", "side_difference_percent"):
        left, right = session.value(measure, "left"), session.value(measure, "right")
        if left is None or right is None:
            return None
        difference = abs(left - right)
        if test == "side_difference_percent":
            mean = (left + right) / 2
            if mean == 0:
                return None
            difference = difference / mean * 100
        if difference >= threshold.value:
            return Indicator(threshold.id, measure, {"left": left, "right": right}, round(difference, 2), threshold)
        return None
    value = session.value(measure)
    if value is None:
        return None
    if (test == "below" and value < threshold.value) or (test == "above" and value > threshold.value):
        return Indicator(threshold.id, measure, {"both": value}, None, threshold)
    return None


def indicators(session: Session, thresholds: list[Threshold], references: list[Reference]) -> list[Indicator]:
    """The session's indicators: each threshold the values are past, then each value outside its reference band."""
    found = [i for t in thresholds if t.test != "min_steps" for i in [_past(t, session)] if i]
    for measure, (_, sided) in MEASURES.items():
        for side in (SIDES if sided else ("both",)):
            value, reference = session.value(measure, side), reference_for(references, measure, side)
            if value is None or reference is None:
                continue
            if (reference.low is not None and value < reference.low) or (
                    reference.high is not None and value > reference.high):
                found.append(Indicator(f"band:{measure}:{side}", measure, {side: value}, None, reference=reference))
    return found


def min_steps(thresholds: list[Threshold]) -> Optional[Threshold]:
    return next((t for t in thresholds if t.test == "min_steps"), None)


# ---- Comparing two sessions -----------------------------------------------------------------------------------

CONDITIONS = ("source", "walkway", "pace", "footwear", "aid")


@dataclass(frozen=True)
class ComparedValue:
    measure: str
    side: str
    first: float
    second: float
    reference: Optional[Reference]

    @property
    def change(self) -> float:
        return round(self.second - self.first, 4)

    @property
    def at_least_smallest_real_change(self) -> Optional[bool]:
        """None: the owner set no smallest real change for it."""
        if self.reference is None or self.reference.smallest_real_change is None:
            return None
        return abs(self.change) >= self.reference.smallest_real_change


def differing_conditions(first: Session, second: Session) -> list[str]:
    """The session conditions that are not the same (as written, ignoring case and spaces at the ends)."""
    def same(a, b) -> bool:
        a, b = getattr(a, "value", a), getattr(b, "value", b)
        return (str(a).strip().lower() if a is not None else None) == (str(b).strip().lower() if b is not None else None)
    return [name for name in CONDITIONS if not same(getattr(first, name), getattr(second, name))]


def compared_values(first: Session, second: Session, references: list[Reference]) -> list[ComparedValue]:
    rows = []
    for measure, (_, sided) in MEASURES.items():
        for side in (SIDES if sided else ("both",)):
            a, b = first.value(measure, side), second.value(measure, side)
            if a is not None and b is not None:
                rows.append(ComparedValue(measure, side, a, b, reference_for(references, measure, side)))
    return rows
