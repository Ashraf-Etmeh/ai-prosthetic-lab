"""The prosthetist's work on a prosthetic case after the intake: modules 1-5 (plan Part 3, 2026-10-24).

From the owner's design (docs/design/02-prosthetics/, SYSTEM_DESIGN.md §6.1):
- Module 1, assessment: what the intake form doesn't hold. The intake's Case stays
  as it is (the golden cases are copies of it), so the rest of the assessment is
  kept here: how each value was measured, joint range and strength as measured,
  signs of infection, the other foot (neuropathy, and whether the diabetic foot
  team cares for it: the draft hard stops read these, prosthetics/hard_stops.py),
  mobility measured with named tests, goals by ICF level (participation and body
  function; activity is the intake's functional goals) and the home and work setting.
- Modules 2-3: what the prosthesis must do (shared/requirements.py), each tied to
  the findings it comes from; then, for each component of the case's level (the
  answer key's categories, prosthetics/component_guide.py COMPONENTS: no new
  vocabulary, owner 2026-10-24), up to three options typed by the prosthetist, side
  by side in the order entered, never ranked: the prosthetist's marks against the
  requirements, what it costs the person, the sources shown that the prosthetist
  links to it, the funding rule and the maker's weight limit as printed, the
  clinic's stock and what to check at fitting. The prosthetist's configuration (one
  option per component) and reason are logged with what was shown (review log).
- Module 4, design and fitting: the six steps, the observation log (what was seen,
  its gait phase, the adjustment made, what was seen after), check-socket versions
  and alignment-record versions (a save never changes an earlier version).
- Module 5: follow-up (shared/followup.py), looping back to module 4, 2-3 or 1.

Nothing here is written, chosen or suggested by code or the AI: every value is the
prosthetist's (SYSTEM_DESIGN.md §1). Nothing typed here is sent to the cloud model
(prosthetics/rag.py case_for_prompt sends only level, side and recorded K-level).
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from prosthetics.case import Case
from prosthetics.component_guide import COMPONENTS
from shared.case_schema import YesNoUnknown, check_number, to_enum
from shared.fitting import GAIT_PHASES, StepStatus
from shared.followup import FollowUp
from shared.forms import MAX_LIST, MAX_ROWS
from shared.requirements import (
    Conflict,
    Finding,
    Mark,
    PlanError,
    Priority,
    Requirement,
    check_conflicts,
    check_requirements,
    next_requirement_id,
    recorded,
    value_at,
)


class FittingStep(str, Enum):
    """Module 4's steps, in order (the design's six)."""

    SHAPE_CAPTURE = "shape_capture"
    CHECK_SOCKET = "check_socket"
    BENCH_ALIGNMENT = "bench_alignment"
    STATIC_ALIGNMENT = "static_alignment"
    DYNAMIC_ALIGNMENT = "dynamic_alignment"
    DELIVERY = "delivery"


OPTION_IDS = ("A", "B", "C")  # the order the prosthetist entered them, never a rank
# Where a follow-up alert may loop back to (the design's "Loop back"): module 4, 2-3 or 1's page.
BACK_TO = ("fitting", "components", "assess")
MAX_MOBILITY = 6  # mobility measures on module 1
MAX_ALIGNMENT_VALUES = 12  # values in one alignment record


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def components_for(case: Case) -> tuple[str, ...]:
    """The component categories of the case's prosthesis, in the answer key's order (component_guide.py)."""
    return tuple(info.key for info in COMPONENTS if case.amputation_level in info.levels)


# ---- Module 1: the assessment beyond the intake form -------------------------------


@dataclass
class MobilityMeasure:
    name: str  # the test, as the prosthetist names it (e.g. a mobility predictor, a timed walk)
    value: str  # as recorded
    how: Optional[str] = None  # e.g. "no walking aid"


@dataclass
class Assessment:
    measured_how: dict[str, str] = field(default_factory=dict)  # value path -> how it was measured, as typed
    joint_range: Optional[str] = None  # as measured, e.g. with a goniometer
    strength: Optional[str] = None  # as measured, e.g. a manual muscle test
    infection: Optional[YesNoUnknown] = None  # signs of infection at the residual limb
    other_foot_neuropathy: Optional[YesNoUnknown] = None  # lower limb: the other foot
    diabetic_foot_team: Optional[YesNoUnknown] = None  # the other foot under the diabetic foot team's care
    mobility: list[MobilityMeasure] = field(default_factory=list)
    mobility_note: Optional[str] = None  # e.g. "with the preparatory prosthesis"
    goal_participation: Optional[str] = None  # goals by ICF level; activity: the intake's functional goals
    goal_body_function: Optional[str] = None
    home_work_setting: Optional[str] = None

    def __post_init__(self) -> None:
        self.infection = to_enum(YesNoUnknown, self.infection)
        self.other_foot_neuropathy = to_enum(YesNoUnknown, self.other_foot_neuropathy)
        self.diabetic_foot_team = to_enum(YesNoUnknown, self.diabetic_foot_team)
        self.mobility = [m if isinstance(m, MobilityMeasure) else MobilityMeasure(**m) for m in self.mobility]
        if len(self.mobility) > MAX_MOBILITY:
            raise PlanError(f"more than {MAX_MOBILITY} mobility measures")
        unknown = set(self.measured_how) - set(MEASURED_PATHS)
        if unknown:
            raise PlanError(f"not a measured value: {sorted(unknown)}")


# The rows of module 1's "Residual limb and body" table, in the design's order: a value of the intake's case,
# or of the assessment ("assessment.<name>"). Each keeps how it was measured (Assessment.measured_how).
MEASURED_PATHS = (
    "residual_limb.wound_status", "assessment.infection", "residual_limb.volume_stability",
    "residual_limb.length_description", "residual_limb.skin_condition", "residual_limb.pain",
    "residual_limb.sensation", "assessment.joint_range", "assessment.strength", "contralateral_limb_status",
    "assessment.other_foot_neuropathy", "assessment.diabetic_foot_team",
)
# Values of the other leg: a lower-limb case only.
OTHER_LEG_PATHS = ("contralateral_limb_status", "assessment.other_foot_neuropathy", "assessment.diabetic_foot_team")


# ---- Modules 2-3: component options ------------------------------------------------


@dataclass
class ComponentOption:
    id: str  # "A", "B" or "C": the order the prosthetist entered them, never a rank
    name: str  # as the prosthetist types it
    marks: dict[str, Mark] = field(default_factory=dict)  # requirement id -> the prosthetist's mark
    mark_notes: dict[str, str] = field(default_factory=dict)  # requirement id -> e.g. "with socks"
    costs: list[str] = field(default_factory=list)  # what it costs the person
    checks: list[str] = field(default_factory=list)  # what to check at fitting
    sources: list[str] = field(default_factory=list)  # ids of the statements shown that the prosthetist links
    funding: Optional[str] = None  # the payer's rule, as the payer prints it
    weight_limit_kg: Optional[float] = None  # the maker's limit, as the maker prints it
    stock: Optional[str] = None  # the clinic's stock and lead time
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        self.marks = {req: Mark(mark) for req, mark in self.marks.items()}
        check_number("weight_limit_kg", self.weight_limit_kg, positive=True)

    def unaddressed(self, requirements: list[Requirement]) -> list[Requirement]:
        """The Must requirements the prosthetist marked this option as not addressing."""
        return [r for r in requirements if r.priority is Priority.MUST and self.marks.get(r.id) is Mark.NO]


# ---- Module 4: design and fitting ---------------------------------------------------


@dataclass
class StepRecord:
    status: StepStatus = StepStatus.NOT_STARTED
    notes: Optional[str] = None  # e.g. "3D scan, approved"

    def __post_init__(self) -> None:
        self.status = StepStatus(self.status)


@dataclass
class Observation:
    step: str  # a FittingStep value
    seen: str  # what was seen, as the prosthetist writes it
    phase: Optional[str] = None  # its gait phase (shared/fitting.py GAIT_PHASES)
    adjustment: Optional[str] = None  # the adjustment the prosthetist made
    seen_after: Optional[str] = None

    def __post_init__(self) -> None:
        FittingStep(self.step)
        if self.phase is not None and self.phase not in GAIT_PHASES:
            raise PlanError(f"not a gait phase: {self.phase!r}")


@dataclass
class SocketVersion:
    number: int  # 1, 2, ...: an added version never changes an earlier one
    seen: str
    changed: Optional[str]
    saved_at: str


@dataclass
class AlignmentVersion:
    number: int  # 1, 2, ...: a save never changes an earlier version
    values: dict[str, str]  # what was aligned -> its value, both as the prosthetist types them, in order
    note: Optional[str]  # why it changed
    saved_at: str
    by: Optional[str] = None  # who saved it, as written


# ---- The plan ---------------------------------------------------------------------


@dataclass
class ProstheticPlan:
    assessment: Assessment = field(default_factory=Assessment)
    requirements: list[Requirement] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    options: dict[str, list[ComponentOption]] = field(default_factory=dict)  # component key -> its options
    configuration: dict[str, str] = field(default_factory=dict)  # component key -> the option id chosen
    choice_reason: Optional[str] = None
    steps: dict[str, StepRecord] = field(default_factory=dict)  # FittingStep value -> its record
    observations: list[Observation] = field(default_factory=list)
    socket_versions: list[SocketVersion] = field(default_factory=list)
    alignment_versions: list[AlignmentVersion] = field(default_factory=list)
    follow_up: FollowUp = field(default_factory=FollowUp)

    def __post_init__(self) -> None:
        wrong = [a.back_to for a in self.follow_up.alerts if a.back_to is not None and a.back_to not in BACK_TO]
        if wrong:
            raise PlanError(f"an alert loops back to one of {BACK_TO}, not {wrong}")

    # ---- Reading ----------------------------------------------------------

    @property
    def chosen(self) -> dict[str, str]:
        """The configuration chosen ({} before any): what the review log's design choice records."""
        return self.configuration

    def requirement(self, requirement_id: str) -> Optional[Requirement]:
        return next((r for r in self.requirements if r.id == requirement_id), None)

    def options_for(self, component: str) -> list[ComponentOption]:
        return self.options.get(component, [])

    def option(self, component: str, option_id: Optional[str]) -> Optional[ComponentOption]:
        return next((o for o in self.options_for(component) if o.id == option_id), None)

    def chosen_option(self, component: str) -> Optional[ComponentOption]:
        return self.option(component, self.configuration.get(component))

    def step(self, step: FittingStep) -> StepRecord:
        return self.steps.get(step.value) or StepRecord()

    @property
    def alignment(self) -> Optional[AlignmentVersion]:
        """The latest alignment record (None before the first save)."""
        return self.alignment_versions[-1] if self.alignment_versions else None

    def next_requirement_id(self) -> str:
        return next_requirement_id(self.requirements)

    # ---- Changing (each checks before it changes anything) ----------------

    def set_assessment(self, assessment: Assessment) -> None:
        self.assessment = assessment

    def set_requirements(self, requirements: list[Requirement], known_findings: set[str]) -> None:
        check_requirements(requirements, known_findings)
        ids = [r.id for r in requirements]
        self.requirements = requirements
        # Marks and conflicts to a requirement that is gone go with it.
        for options in self.options.values():
            for option in options:
                option.marks = {req: mark for req, mark in option.marks.items() if req in ids}
                option.mark_notes = {req: note for req, note in option.mark_notes.items() if req in ids}
        self.conflicts = [c for c in self.conflicts if c.first in ids and c.second in ids]

    def set_conflicts(self, conflicts: list[Conflict]) -> None:
        check_conflicts(conflicts, self.requirements)
        self.conflicts = conflicts

    def set_options(self, component: str, options: list[ComponentOption], components: tuple[str, ...],
                    known_sources: set[str]) -> None:
        """One component's options. `components`: the case's categories; `known_sources`: the ids of the
        statements shown for this component (a source the page didn't show can't be linked)."""
        if component not in components:
            raise PlanError(f"not a component of this case: {component!r}")
        ids = [o.id for o in options]
        if len(ids) != len(set(ids)) or not set(ids) <= set(OPTION_IDS):
            raise PlanError(f"option ids must be distinct, from {OPTION_IDS}")
        known = {r.id for r in self.requirements}
        for option in options:
            if not option.name.strip():
                raise PlanError(f"option {option.id}: no name")
            if len(option.costs) > MAX_LIST or len(option.checks) > MAX_LIST:
                raise PlanError(f"option {option.id}: more than {MAX_LIST} lines")
            if (set(option.marks) | set(option.mark_notes)) - known:
                raise PlanError(f"option {option.id}: not a requirement")
            if set(option.sources) - known_sources:
                raise PlanError(f"option {option.id}: not a source shown for {component}")
        before = self.chosen_option(component)
        if options:
            self.options[component] = options
        else:
            self.options.pop(component, None)
        after = self.chosen_option(component)
        # The reason was given for that configuration: if a chosen option was removed or renamed, the choice
        # goes with it (the review log keeps it as it was made). New marks, notes or costs keep it.
        if before is not None and (after is None or after.name != before.name):
            self.configuration, self.choice_reason = {}, None

    def choose(self, configuration: dict[str, str], reason: str) -> None:
        """The prosthetist's configuration: one option per component (at least one), with the reason."""
        configuration = {component: option_id for component, option_id in configuration.items() if option_id}
        if not configuration:
            raise PlanError("a configuration needs at least one option")
        for component, option_id in configuration.items():
            if self.option(component, option_id) is None:
                raise PlanError(f"no option {option_id!r} for {component!r}")
        if not reason.strip():
            raise PlanError("a configuration needs its reason")
        self.configuration, self.choice_reason = configuration, reason.strip()

    def set_steps(self, steps: dict[FittingStep, StepRecord]) -> None:
        self.steps = {step.value: record for step, record in steps.items()}

    def set_observations(self, observations: list[Observation]) -> None:
        if len(observations) > MAX_ROWS:
            raise PlanError(f"more than {MAX_ROWS} observations")
        self.observations = observations

    def add_socket_version(self, seen: str, changed: Optional[str]) -> SocketVersion:
        if not seen.strip():
            raise PlanError("a check-socket version says what was seen")
        version = SocketVersion(len(self.socket_versions) + 1, seen.strip(), (changed or "").strip() or None, _now())
        self.socket_versions.append(version)
        return version

    def save_alignment(self, values: dict[str, str], note: Optional[str], by: Optional[str] = None) -> AlignmentVersion:
        """Keep the values as a new version. Values left empty are not kept; nothing new is not saved."""
        values = {name.strip(): value.strip() for name, value in values.items()
                  if name and name.strip() and value and value.strip()}
        if len(values) > MAX_ALIGNMENT_VALUES:
            raise PlanError(f"more than {MAX_ALIGNMENT_VALUES} values")
        if not values or (self.alignment is not None and values == self.alignment.values):
            raise PlanError("no change since the last version")
        version = AlignmentVersion(len(self.alignment_versions) + 1, values, (note or "").strip() or None, _now(),
                                   (by or "").strip() or None)
        self.alignment_versions.append(version)
        return version

    # ---- Files --------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        assessment = asdict(self.assessment)
        for name in ("infection", "other_foot_neuropathy", "diabetic_foot_team"):
            value = getattr(self.assessment, name)
            assessment[name] = value.value if value else None
        return {
            "assessment": assessment,
            "requirements": [{"id": r.id, "text": r.text, "findings": list(r.findings),
                              "priority": r.priority.value if r.priority else None} for r in self.requirements],
            "conflicts": [{"first": c.first, "second": c.second, "note": c.note} for c in self.conflicts],
            "options": {component: [{**asdict(o), "marks": {req: mark.value for req, mark in o.marks.items()}}
                                    for o in options] for component, options in self.options.items()},
            "configuration": dict(self.configuration),
            "choice_reason": self.choice_reason,
            "steps": {name: {"status": s.status.value, "notes": s.notes} for name, s in self.steps.items()},
            "observations": [asdict(o) for o in self.observations],
            "socket_versions": [asdict(v) for v in self.socket_versions],
            "alignment_versions": [asdict(v) for v in self.alignment_versions],
            "follow_up": self.follow_up.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProstheticPlan":
        """A saved plan; a key it doesn't have gets its default."""
        return cls(
            assessment=Assessment(**(data.get("assessment") or {})),
            requirements=[Requirement(**r) for r in data.get("requirements", [])],
            conflicts=[Conflict(**c) for c in data.get("conflicts", [])],
            options={component: [ComponentOption(**o) for o in options]
                     for component, options in (data.get("options") or {}).items()},
            configuration=dict(data.get("configuration") or {}),
            choice_reason=data.get("choice_reason"),
            steps={name: StepRecord(**s) for name, s in (data.get("steps") or {}).items()},
            observations=[Observation(**o) for o in data.get("observations", [])],
            socket_versions=[SocketVersion(**v) for v in data.get("socket_versions", [])],
            alignment_versions=[AlignmentVersion(**v) for v in data.get("alignment_versions", [])],
            follow_up=FollowUp.from_dict(data.get("follow_up")),
        )


# ---- The case's findings a requirement can come from ------------------------------

# Recorded values a requirement may come from, by group: the residual limb and body (the intake and the
# assessment), then goals, function and setting. A path "assessment.<name>" is the plan's, else the case's.
_BODY_PATHS = ("residual_limb.wound_status", "residual_limb.volume_stability", "residual_limb.length_description",
               "residual_limb.skin_condition", "residual_limb.pain", "residual_limb.sensation", "assessment.joint_range",
               "assessment.strength", "contralateral_limb_status", "assessment.other_foot_neuropathy",
               "cognitive_status", "comorbidities", "body_weight_kg")
_GOAL_PATHS = ("activity.k_level", "activity.description", "activity.functional_goals", "assessment.goal_participation",
               "assessment.goal_body_function", "assessment.home_work_setting", "prior_devices")
FINDING_GROUPS = ("body", "goals", "missing")  # the requirements page's groups ("req_group.<group>")


def finding_paths(case: Case) -> tuple[str, ...]:
    """The values a requirement of this case may come from (the other leg and the K-level: lower limb only)."""
    skip = set() if case.is_lower_limb else {"activity.k_level", *OTHER_LEG_PATHS}
    return tuple(path for path in _BODY_PATHS + _GOAL_PATHS if path not in skip)


def value_of(case: Case, plan: Optional[ProstheticPlan], path: str):
    """A value of the case, or of the plan's assessment ("assessment.<name>"; None without a plan)."""
    if path.startswith("assessment."):
        return value_at(plan, path) if plan is not None else None
    return value_at(case, path)


def case_findings(case: Case, plan: Optional[ProstheticPlan]) -> list[Finding]:
    """What the case and its assessment recorded that a requirement can come from (recorded values only)."""
    findings = []
    for group, paths in (("body", _BODY_PATHS), ("goals", _GOAL_PATHS)):
        for path in paths:
            if path in finding_paths(case):
                value = value_of(case, plan, path)
                if recorded(value):
                    findings.append(Finding(path, group, path, value))
    return findings


def missing_findings(case: Case, plan: Optional[ProstheticPlan]) -> list[Finding]:
    """The values a requirement can come from that aren't recorded yet (a requirement on one is provisional)."""
    return [Finding(path, "missing", path, None) for path in finding_paths(case)
            if not recorded(value_of(case, plan, path))]


def linkable(case: Case) -> set[str]:
    """Every key a requirement of this case may name: each value, recorded or not."""
    return set(finding_paths(case))


def waiting_on(requirement: Requirement, case: Case, plan: Optional[ProstheticPlan]) -> list[str]:
    """The values the requirement names that aren't recorded yet: while any is, it is provisional."""
    return [key for key in requirement.findings
            if key in finding_paths(case) and not recorded(value_of(case, plan, key))]


# The class a saved plan is read back with (shared/store.py, through shared/domains.py).
PLAN = ProstheticPlan
