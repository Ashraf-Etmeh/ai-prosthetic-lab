"""Follow-up and evaluation (SYSTEM_DESIGN.md §5), shared by every domain's follow-up module.

The visits with their dates, the outcome measures the clinician enters at each
visit, wearing time and the device's condition, and alerts in the clinician's
words that loop back to the module where the fix would happen (built for
orthotics module 6 on 2026-10-23; the domain says where an alert may loop back
to, e.g. orthotics/plan.py BACK_TO).

The visits belong to one case, whose id is random (no patient identifiers): the case
is the pseudonymous link between visits. Every value is shown as recorded and the
clinician judges the change; the tool computes no change, score or trend. The only
thing it works out is which review is due next, from the visits' own status and date.
"""

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional

from shared.dates import check_date


class VisitStatus(str, Enum):
    DONE = "done"
    DUE = "due"
    NOT_BOOKED = "not_booked"


@dataclass
class MeasureDef:
    name: str  # e.g. "Gait speed, 10-metre walk"
    unit: Optional[str] = None  # e.g. "m/s"
    how: Optional[str] = None  # e.g. "same cane, comfortable pace"


@dataclass
class Visit:
    name: str  # e.g. "6-week review"
    date: Optional[str] = None  # YYYY-MM-DD
    status: VisitStatus = VisitStatus.NOT_BOOKED
    values: dict[str, str] = field(default_factory=dict)  # measure name -> the value as entered
    wearing: Optional[str] = None  # wearing time, as the patient reports it
    puts_on_alone: Optional[str] = None
    device_condition: Optional[str] = None
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        self.status = VisitStatus(self.status)
        self.date = check_date(self.date)


@dataclass
class Alert:
    text: str  # in the clinician's words
    back_to: Optional[str] = None  # the module it loops back to: one the domain allows (its plan checks)
    resolved: bool = False


@dataclass
class FollowUp:
    measures: list[MeasureDef] = field(default_factory=list)
    visits: list[Visit] = field(default_factory=list)
    alerts: list[Alert] = field(default_factory=list)
    due_next: Optional[str] = None  # what is due at the next review, e.g. "device satisfaction"

    def __post_init__(self) -> None:
        self.measures = [m if isinstance(m, MeasureDef) else MeasureDef(**m) for m in self.measures]
        self.visits = [v if isinstance(v, Visit) else Visit(**v) for v in self.visits]
        self.alerts = [a if isinstance(a, Alert) else Alert(**a) for a in self.alerts]

    def next_due(self) -> Optional[Visit]:
        """The first visit marked due, by date (one without a date last)."""
        due = [v for v in self.visits if v.status is VisitStatus.DUE]
        return min(due, key=lambda v: (v.date is None, v.date or ""), default=None)

    def series(self, measure: str) -> list[tuple[Visit, Optional[float], str]]:
        """Each done visit with a value for the measure: (visit, the value as a number if it is one, as entered)."""
        rows = []
        for visit in self.visits:
            raw = visit.values.get(measure)
            if raw is None:
                continue
            try:
                number: Optional[float] = float(raw.replace(",", "."))
            except ValueError:
                number = None
            rows.append((visit, number, raw))
        return rows

    def latest(self) -> Optional[Visit]:
        """The last visit marked done (the wearing and device card shows its values)."""
        done = [v for v in self.visits if v.status is VisitStatus.DONE]
        return done[-1] if done else None

    @property
    def empty(self) -> bool:
        return self == FollowUp()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for visit in data["visits"]:
            visit["status"] = VisitStatus(visit["status"]).value
        return data

    @classmethod
    def from_dict(cls, data: Optional[dict[str, Any]]) -> "FollowUp":
        return cls(**(data or {}))
