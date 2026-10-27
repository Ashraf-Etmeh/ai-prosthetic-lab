"""A case's rehabilitation (SYSTEM_DESIGN.md §6.4; docs/design/05-rehabilitation/; plan Part 9, 2026-10-27).

Rehabilitation works on a case of either domain (the design's example is an orthotic stroke case with its AFO):
it has no intake of its own, and its plan is kept with the case (shared/store.py CaseRecord.rehab, case file
version 5). Every value here is the team's: the goals agreed with the person, the interventions and their doses
(the therapist's), the phases and the team, the progress measures and the goal attainment scores (the therapist
with the person), the training tasks, the home programme (the therapist's words, in Arabic and English), what was
seen in training for the device specialist, the team's entries, the handover (written by a person and signed;
SYSTEM_DESIGN.md §11.8: no AI draft until the owner decides) and the next steps. The tool writes, scores, doses and
ranks nothing. Nothing here is sent to a language model.

PROPOSAL (Claude, 2026-10-27, awaiting the owner and a therapist): the vocabularies below (intervention kinds, team
roles, task statuses, kinds of entry) follow the design's screens and common rehabilitation records; the owner may
revise them.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from shared.dates import check_date
from shared.followup import FollowUp


class PlanError(ValueError):
    """A rehabilitation plan that can't be kept as it is."""


class IcfLevel(str, Enum):
    PARTICIPATION = "participation"
    ACTIVITY = "activity"
    BODY_FUNCTION = "body_function"


class InterventionKind(str, Enum):
    GAIT_TRAINING = "gait_training"
    BALANCE_TRAINING = "balance_training"
    STRENGTH_TRAINING = "strength_training"
    TREADMILL_TRAINING = "treadmill_training"
    DEVICE_USE = "device_use"  # putting the device on and off, wearing schedule, care
    TASK_PRACTICE = "task_practice"  # daily activities
    LIMB_CARE = "limb_care"  # residual limb: skin, oedema, compression, desensitisation
    MIRROR_THERAPY = "mirror_therapy"  # phantom limb pain
    HOME_PROGRAMME = "home_programme"
    FALLS_PREVENTION = "falls_prevention"
    OTHER = "other"  # the therapist's own: never searched ("No source in the library: the therapist's own")


class Phase(str, Enum):
    INPATIENT = "inpatient"
    OUTPATIENT = "outpatient"
    COMMUNITY = "community"


class PhaseStatus(str, Enum):
    NOT_STARTED = "not_started"
    CURRENT = "current"
    DONE = "done"


class TeamRole(str, Enum):
    PHYSIOTHERAPIST = "physiotherapist"
    OCCUPATIONAL_THERAPIST = "occupational_therapist"
    PROSTHETIST = "prosthetist"
    ORTHOTIST = "orthotist"
    REHAB_PHYSICIAN = "rehab_physician"
    NURSE = "nurse"
    PSYCHOLOGIST = "psychologist"
    OTHER = "other"


class TaskStatus(str, Enum):
    NOT_STARTED = "not_started"
    WITH_HELP = "with_help"
    WITH_CUES = "with_cues"
    INDEPENDENT = "independent"


class EntryKind(str, Enum):
    THERAPY = "therapy"
    DEVICE = "device"
    MEDICAL = "medical"


SCORES = (-2, -1, 0, 1, 2)  # goal attainment, scored by the therapist with the person
# The modules a progress alert may loop back to (shared/followup.py Alert.back_to; rehabilitation/routes.py).
BACK_TO = ("plan", "training")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _enum(cls, value):
    return value if value is None or isinstance(value, cls) else cls(value)


@dataclass
class Goal:
    id: str  # "G1", ...: a new goal takes the number after the highest in use
    level: IcfLevel
    text: str  # as agreed with the person
    within: Optional[str] = None  # the timeframe, as written (e.g. "12 weeks")
    review_on: Optional[str] = None  # YYYY-MM-DD

    def __post_init__(self) -> None:
        self.level = _enum(IcfLevel, self.level)
        check_date(self.review_on)


@dataclass
class GoalScore:
    goal: str  # a goal id
    score: int  # -2 to +2
    on: str  # YYYY-MM-DD
    note: Optional[str] = None

    def __post_init__(self) -> None:
        if self.score not in SCORES:
            raise PlanError(f"a goal attainment score is one of {SCORES}, got {self.score!r}")
        check_date(self.on)


@dataclass
class Intervention:
    id: str  # "I1", ...
    kind: InterventionKind
    name: Optional[str] = None  # the therapist's words (needed for "other")
    goals: list[str] = field(default_factory=list)  # the goal ids it serves
    dose: Optional[str] = None  # set by the therapist, as written

    def __post_init__(self) -> None:
        self.kind = _enum(InterventionKind, self.kind)


@dataclass
class PhaseRecord:
    status: PhaseStatus = PhaseStatus.NOT_STARTED
    when: Optional[str] = None  # as written (e.g. "weeks 1-12, now week 6")

    def __post_init__(self) -> None:
        self.status = _enum(PhaseStatus, self.status)


@dataclass
class TeamMember:
    role: TeamRole
    does: Optional[str] = None  # e.g. "plan owner", "G1, G3", as written

    def __post_init__(self) -> None:
        self.role = _enum(TeamRole, self.role)


@dataclass
class TrainingTask:
    id: str  # "T1", ...
    text: str
    trains: list[str] = field(default_factory=list)  # requirement ids of the device's plan (R1 ...) or goal ids
    stage: Optional[str] = None  # as written (e.g. "parallel bars, then open floor")
    status: TaskStatus = TaskStatus.NOT_STARTED

    def __post_init__(self) -> None:
        self.status = _enum(TaskStatus, self.status)


@dataclass
class Observation:
    """Seen in training, for the device specialist (the design's "orthotist's queue"). Added, never changed; the
    specialist's answer is added to it."""

    text: str
    for_role: TeamRole
    at: str
    answer: Optional[str] = None
    answered_at: Optional[str] = None

    def __post_init__(self) -> None:
        self.for_role = _enum(TeamRole, self.for_role)


@dataclass
class TeamEntry:
    """What one professional recorded: added, never changed (the team record)."""

    on: str  # YYYY-MM-DD
    role: TeamRole
    kind: EntryKind
    text: str
    at: str  # when it was added

    def __post_init__(self) -> None:
        self.role = _enum(TeamRole, self.role)
        self.kind = _enum(EntryKind, self.kind)
        check_date(self.on)


@dataclass
class Handover:
    """One version of the handover summary, written by a person; once signed it is final (a change is a new
    version)."""

    number: int
    text: str
    written_by: TeamRole
    saved_at: str
    signed_at: Optional[str] = None
    signed_by: Optional[TeamRole] = None

    def __post_init__(self) -> None:
        self.written_by = _enum(TeamRole, self.written_by)
        self.signed_by = _enum(TeamRole, self.signed_by)


@dataclass
class NextStep:
    text: str
    on: Optional[str] = None
    done: bool = False

    def __post_init__(self) -> None:
        check_date(self.on)


@dataclass
class RehabPlan:
    agreed_on: Optional[str] = None  # the goals were agreed with the person on
    review_every: Optional[str] = None  # as written (e.g. "4 weeks")
    goals: list[Goal] = field(default_factory=list)
    scores: list[GoalScore] = field(default_factory=list)  # added, never changed
    interventions: list[Intervention] = field(default_factory=list)
    phases: dict[str, PhaseRecord] = field(default_factory=dict)  # Phase value -> its record
    team: list[TeamMember] = field(default_factory=list)
    follow_up: FollowUp = field(default_factory=FollowUp)  # progress: measures, sessions, alerts
    tasks: list[TrainingTask] = field(default_factory=list)
    home_en: Optional[str] = None  # the home programme, the therapist's words
    home_ar: Optional[str] = None
    home_checked_by: Optional[str] = None  # the Arabic-reading therapist who checked the Arabic text
    observations: list[Observation] = field(default_factory=list)
    entries: list[TeamEntry] = field(default_factory=list)
    handovers: list[Handover] = field(default_factory=list)
    next_steps: list[NextStep] = field(default_factory=list)

    def __post_init__(self) -> None:
        check_date(self.agreed_on)
        self.goals = [g if isinstance(g, Goal) else Goal(**g) for g in self.goals]
        self.scores = [s if isinstance(s, GoalScore) else GoalScore(**s) for s in self.scores]
        self.interventions = [i if isinstance(i, Intervention) else Intervention(**i) for i in self.interventions]
        self.phases = {Phase(k).value: (v if isinstance(v, PhaseRecord) else PhaseRecord(**v))
                       for k, v in self.phases.items()}
        self.team = [m if isinstance(m, TeamMember) else TeamMember(**m) for m in self.team]
        if not isinstance(self.follow_up, FollowUp):
            self.follow_up = FollowUp.from_dict(self.follow_up)
        self.tasks = [t if isinstance(t, TrainingTask) else TrainingTask(**t) for t in self.tasks]
        self.observations = [o if isinstance(o, Observation) else Observation(**o) for o in self.observations]
        self.entries = [e if isinstance(e, TeamEntry) else TeamEntry(**e) for e in self.entries]
        self.handovers = [h if isinstance(h, Handover) else Handover(**h) for h in self.handovers]
        self.next_steps = [s if isinstance(s, NextStep) else NextStep(**s) for s in self.next_steps]
        ids = [g.id for g in self.goals]
        if len(set(ids)) != len(ids):
            raise PlanError("each goal has its own id")
        known = set(ids)
        for item in self.interventions:
            if set(item.goals) - known:
                raise PlanError(f"intervention {item.id} names a goal that is not in the plan")
            if item.kind is InterventionKind.OTHER and not item.name:
                raise PlanError(f"intervention {item.id}: the therapist's own intervention needs its name")

    # ---- Reading it ----

    def goal_ids(self) -> list[str]:
        return [g.id for g in self.goals]

    def scores_for(self, goal_id: str) -> list[GoalScore]:
        return [s for s in self.scores if s.goal == goal_id]

    def latest_score(self, goal_id: str) -> Optional[GoalScore]:
        scores = self.scores_for(goal_id)
        return max(scores, key=lambda s: s.on) if scores else None

    def phase(self, phase: str) -> PhaseRecord:
        return self.phases.get(phase) or PhaseRecord()

    def open_observations(self) -> list[Observation]:
        return [o for o in self.observations if not o.answered_at]

    @property
    def handover(self) -> Optional[Handover]:
        return self.handovers[-1] if self.handovers else None

    @property
    def empty(self) -> bool:
        return self.to_dict() == RehabPlan().to_dict()

    # ---- Keeping it ----

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["follow_up"] = self.follow_up.to_dict()
        for key in ("goals", "interventions", "team", "tasks", "observations", "entries", "handovers"):
            for item in data[key]:
                for name, value in item.items():
                    if isinstance(value, Enum):
                        item[name] = value.value
        data["phases"] = {k: {"status": v.status.value, "when": v.when} for k, v in self.phases.items()}
        return data

    @classmethod
    def from_dict(cls, data: Optional[dict[str, Any]]) -> "RehabPlan":
        return cls(**(data or {}))


def next_id(prefix: str, ids: list[str]) -> str:
    """The next free "<prefix><n>" after the highest number in use (like shared/requirements.py)."""
    numbers = [int(i[len(prefix):]) for i in ids if i.startswith(prefix) and i[len(prefix):].isdigit()]
    return f"{prefix}{max(numbers, default=0) + 1}"
