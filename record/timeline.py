"""What one person's record shows (SYSTEM_DESIGN.md §7.4; docs/design/09-patient-record/Main.html; plan Part 8):
the timeline across domains, the outcome measures, the follow-up schedule and the summary, all gathered from the
cases attached to the person, as their specialists recorded them.

Every item is what was recorded, with its date, opening the page where it was recorded. Nothing is worked out
from a value: no change, score or trend (each measure keeps how it was measured and when; who measured it is not
recorded until roles and sign-in come). The only things counted are dates and statuses: which review is due next,
and whether its date has passed. Each domain says what its plan keeps in versions and which page a choice or a
visit opens (<domain>/nav.py RECORD_VERSIONS, RECORD_CHOICE, RECORD_FOLLOW_UP); this file names no domain.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from record.people import Person
from review.decision_log import DESIGN_CHOICE, read_decisions
from shared import domains
from shared.followup import FollowUp, VisitStatus
from shared.store import CaseRecord, store


@dataclass(frozen=True)
class Event:
    """One item of the timeline."""

    at: str  # a date (YYYY-MM-DD) or a time (ISO 8601): sorted as text, newest first
    domain: str
    kind: str  # intake, review, choice, version, visit; rehab_plan, rehab_score, team_entry, handover
    case_id: str
    endpoint: str  # the page it opens
    label: Optional[str] = None  # a version's text key, a visit's name as typed, a decision
    number: Optional[int] = None  # a version's number
    status: Optional[str] = None  # a visit's status (VisitStatus value)
    note: Optional[str] = None  # a design choice's reason, as written

    @property
    def day(self) -> str:
        return self.at[:10]


@dataclass(frozen=True)
class ScheduledVisit:
    domain: str
    case_id: str
    name: str
    date: Optional[str]
    status: str
    endpoint: str

    @property
    def date_passed(self) -> bool:
        """A visit still due whose date is before today (a date comparison, nothing more)."""
        return self.status == VisitStatus.DUE.value and bool(self.date) and self.date < date.today().isoformat()


@dataclass(frozen=True)
class MeasureTable:
    """One case's outcome measures: each measure (name, unit, how) by visit, the values as entered."""

    domain: str
    case_id: str
    columns: list[tuple[str, Optional[str]]]  # (visit name, date) for each visit with a value
    rows: list[tuple[str, Optional[str], Optional[str], list[Optional[str]]]]  # name, unit, how, value per column


@dataclass
class RecordView:
    person: Person
    records: list[tuple[str, Optional[CaseRecord]]]  # (case id, the case; None: its file is not on this machine)
    events: list[Event] = field(default_factory=list)
    schedule: list[ScheduledVisit] = field(default_factory=list)
    measures: list[MeasureTable] = field(default_factory=list)
    open_alerts: list[tuple[str, str, str]] = field(default_factory=list)  # (domain, case id, the alert's words)
    latest_choice: Optional[Event] = None

    @property
    def next_due(self) -> Optional[ScheduledVisit]:
        due = [v for v in self.schedule if v.status == VisitStatus.DUE.value]
        return min(due, key=lambda v: (v.date is None, v.date or ""), default=None)

    def domains_here(self) -> list[str]:
        return [d for d in domains.DOMAINS if any(r and r.case.domain == d for _, r in self.records)]


def _follow_up(record: CaseRecord) -> FollowUp:
    return getattr(record.plan, "follow_up", None) or FollowUp()


def record_view(person: Person) -> RecordView:
    """Everything the person's record page shows, from the attached cases."""
    view = RecordView(person, [(case_id, store.get(case_id)) for case_id in person.case_ids()])
    for case_id, record in view.records:
        if record is None:
            continue
        domain = record.case.domain
        nav = domains.part(domain, "nav")
        first = nav.MODULES[0][1]
        view.events.append(Event(record.case.created_at, domain, "intake", case_id, first))
        for entry in read_decisions(case_id):
            if entry["decision"] == DESIGN_CHOICE:
                view.events.append(Event(entry["logged_at"], domain, "choice", case_id, nav.RECORD_CHOICE,
                                         note=entry.get("note")))
            else:
                view.events.append(Event(entry["logged_at"], domain, "review", case_id, "review.show_case",
                                         label=entry["decision"]))
        for name, text_key, page in nav.RECORD_VERSIONS:
            for version in getattr(record.plan, name, None) or []:
                view.events.append(Event(version.saved_at, domain, "version", case_id, page, label=text_key,
                                         number=version.number))
        follow_up = _follow_up(record)
        for visit in follow_up.visits:
            status = VisitStatus(visit.status).value
            view.schedule.append(ScheduledVisit(domain, case_id, visit.name, visit.date, status, nav.RECORD_FOLLOW_UP))
            if visit.date:
                view.events.append(Event(visit.date, domain, "visit", case_id, nav.RECORD_FOLLOW_UP, label=visit.name,
                                         status=status))
        view.open_alerts += [(domain, case_id, alert.text) for alert in follow_up.alerts if not alert.resolved]
        rehab = record.rehab  # its rehabilitation (rehabilitation/plan.py; plan Part 9)
        if rehab is not None:
            if rehab.agreed_on:
                view.events.append(Event(rehab.agreed_on, domain, "rehab_plan", case_id, "rehab.plan"))
            view.events += [Event(s.on, domain, "rehab_score", case_id, "rehab.progress", label=s.goal,
                                  number=s.score) for s in rehab.scores]
            view.events += [Event(e.on, domain, "team_entry", case_id, "rehab.team", label=e.role.value, note=e.text)
                            for e in rehab.entries]
            view.events += [Event(h.signed_at, domain, "handover", case_id, "rehab.team", label=h.signed_by.value,
                                  number=h.number) for h in rehab.handovers if h.signed_at]
        columns = [v for v in follow_up.visits if v.values]
        if follow_up.measures and columns:
            view.measures.append(MeasureTable(
                domain, case_id, [(v.name, v.date) for v in columns],
                [(m.name, m.unit, m.how, [v.values.get(m.name) for v in columns]) for m in follow_up.measures]))
    view.events.sort(key=lambda e: e.at, reverse=True)
    choices = [e for e in view.events if e.kind == "choice"]
    view.latest_choice = choices[0] if choices else None
    return view
