"""The orthotist's work on an orthotic case after its analysis: modules 2-6 (2026-10-23).

From the owner's "Orthotics Module Design" canvas, after module 1 (functional case
analysis: the intake form and the analysis page):
- Module 2, requirements: what the orthosis must do, in the orthotist's words,
  each tied to what it comes from in the case (a gait deviation, an exam value, a
  goal, or a value not recorded yet: the requirement is then provisional), with
  the orthotist's priority, and the conflicts between requirements as the
  orthotist notes them.
- Module 3, design options ("choosing and designing orthotic devices" and
  "linking the case to components and materials"): up to three options, each a
  device type with its materials and parts (each part tied to the requirements
  it serves), the orthotist's marks of which requirements it addresses, what it
  costs the patient, the clinic's stock and what to check at fitting; and the
  referral to discuss FES with the rehabilitation team. Shown side by side in
  the order entered, never ranked; the orthotist chooses and gives the reason
  (review log).
- Module 4, digital design ("supporting the digital design workflow"): six steps
  from capture to release, the simulation results and pressure hot spots as
  entered from the CAD tool, and the design parameters, each with its basis and
  the requirements it serves, every save a new version, each value approved by
  the orthotist; sending to manufacture once all are approved.
- Modules 5 and 6: orthotics/fit.py and the shared follow-up records (shared/followup.py).

Requirements, priorities, marks and conflicts are shared with every domain
(shared/requirements.py).

Nothing here is written, chosen or suggested by code or the AI: every value is
the orthotist's (owner's decision 2026-10-23, and docs/design/SYSTEM_DESIGN.md §11.7: the design's screens, filled by the
orthotist where the design shows a suggestion). The vocabularies below (device
types, parts, steps, methods, parameters, bases) are a PROPOSAL awaiting the
owner and an orthotist; only their fixed words are ever searched
(orthotics/sources.py), never what the orthotist typed.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from orthotics.case import OrthoticCase
from orthotics.fit import FitRecord
from shared.fitting import StepStatus  # noqa: F401  (every domain's; kept here by name)
from shared.followup import FollowUp
from shared.forms import MAX_LIST, MAX_TEXT  # noqa: F401  (MAX_TEXT: the orthotic pages' limit, kept by name)
from shared.requirements import (  # noqa: F401  (Finding, PlanError, value_at, recorded: kept here by name)
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


class DeviceType(str, Enum):
    SOLID_AFO = "solid_afo"
    HINGED_AFO = "hinged_afo"  # articulated, ankle joints, usually a plantarflexion stop
    FLEXIBLE_AFO = "flexible_afo"
    POSTERIOR_LEAF_SPRING = "posterior_leaf_spring"
    CARBON_AFO = "carbon_afo"
    ANTERIOR_SHELL_AFO = "anterior_shell_afo"  # ICRC's anti-talus AFO
    PRINTED_AFO = "printed_afo"  # 3D-printed
    PREFABRICATED_AFO = "prefabricated_afo"
    FES = "fes"  # functional electrical stimulation of the peroneal nerve


class Part(str, Enum):
    """Materials and components an option is made of."""

    POLYPROPYLENE_SHELL = "polypropylene_shell"
    CARBON_COMPOSITE = "carbon_composite"
    PRINTED_SHELL = "printed_shell"
    EVA_LINING = "eva_lining"
    ANKLE_JOINTS = "ankle_joints"
    PLANTARFLEXION_STOP = "plantarflexion_stop"
    POSTERIOR_REINFORCEMENT = "posterior_reinforcement"
    STRAPS = "straps"
    HEEL_WEDGE = "heel_wedge"
    FOOTWEAR = "footwear"


class Step(str, Enum):
    """The design and fabrication workflow, in order (the design's six steps)."""

    CAPTURE = "capture"
    RECTIFY = "rectify"
    PARAMETERS = "parameters"
    SIMULATE = "simulate"  # added 2026-10-23 (the design's step 4)
    FABRICATE = "fabricate"  # shown as "Manufacture"
    RELEASE = "release"


class Method(str, Enum):
    PLASTER_CAST = "plaster_cast"
    SCAN_3D = "scan_3d"
    MEASUREMENTS = "measurements"
    PLASTER_MODEL = "plaster_model"
    CAD = "cad"
    FEA = "fea"  # a finite-element or pressure simulation in the CAD tool
    THERMOFORMING = "thermoforming"
    PRINTING_3D = "printing_3d"
    PREFABRICATED = "prefabricated"


class Basis(str, Enum):
    """Where a parameter value comes from, as the orthotist records it (the design's tags)."""

    ORTHOTIST = "orthotist"  # set by the orthotist
    PRACTICE_RULE = "practice_rule"  # a practice rule, named in the basis note
    SCAN = "scan"  # measured on the scan


# The methods a step can be done with (a step with none has no method to choose).
STEP_METHODS: dict[Step, tuple[Method, ...]] = {
    Step.CAPTURE: (Method.PLASTER_CAST, Method.SCAN_3D, Method.MEASUREMENTS),
    Step.RECTIFY: (Method.PLASTER_MODEL, Method.CAD),
    Step.PARAMETERS: (),
    Step.SIMULATE: (Method.FEA,),
    Step.FABRICATE: (Method.THERMOFORMING, Method.PRINTING_3D, Method.PREFABRICATED),
    Step.RELEASE: (),
}

# Design parameters the orthotist records, in the order shown. Values are as typed.
PARAMETERS = ("ankle_angle", "plantarflexion_stop", "joint_axis", "trim_lines", "footplate", "shell", "lining",
              "closure", "joints", "heel_wedge")

OPTION_IDS = ("A", "B", "C")
# Where a follow-up alert may loop back to (the design's "Loop back"): module 5, 3 or 1's page.
BACK_TO = ("fit", "options", "analysis")
FES_REFERRAL = "F"  # the referral to discuss FES: chosen like an option (the design's fourth card)
MAX_PARTS_PER_OPTION = 6


def _enum(cls, value):
    return None if value is None else cls(value)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _design(option: "DesignOption") -> tuple:
    """What an option is: its device and its parts (not the orthotist's marks or notes on it)."""
    return option.device, sorted(part.part.value for part in option.parts)


@dataclass
class OptionPart:
    part: Part
    requirements: list[str] = field(default_factory=list)  # the requirement ids it serves
    note: Optional[str] = None  # e.g. "thickness by body weight (practice rule)"

    def __post_init__(self) -> None:
        self.part = Part(self.part)


@dataclass
class DesignOption:
    id: str  # "A", "B" or "C": the order the orthotist entered them, never a rank
    device: DeviceType
    parts: list[OptionPart] = field(default_factory=list)
    marks: dict[str, Mark] = field(default_factory=dict)  # requirement id -> the orthotist's mark
    notes: Optional[str] = None
    summary: Optional[str] = None  # under the device's name, e.g. "Stop set at the calf length, dorsiflexion free"
    mark_notes: dict[str, str] = field(default_factory=dict)  # requirement id -> e.g. "adjustable", "with lining"
    costs: list[str] = field(default_factory=list)  # what it costs the patient
    checks: list[str] = field(default_factory=list)  # what to check at fitting
    stock: Optional[str] = None  # the clinic's stock, e.g. "joints in stock", "6-week order"

    def __post_init__(self) -> None:
        self.device = DeviceType(self.device)
        self.parts = [p if isinstance(p, OptionPart) else OptionPart(**p) for p in self.parts]
        self.marks = {req: Mark(mark) for req, mark in self.marks.items()}

    def unaddressed(self, requirements: list[Requirement]) -> list[Requirement]:
        """The Must requirements the orthotist marked this option as not addressing."""
        return [r for r in requirements if r.priority is Priority.MUST and self.marks.get(r.id) is Mark.NO]

    def has(self, part: Part) -> bool:
        return any(p.part is part for p in self.parts)


@dataclass
class FesReferral:
    """The referral to discuss FES with the rehabilitation team (the design's FES card)."""

    checks: list[str] = field(default_factory=list)  # what to check first, in the orthotist's words
    note: Optional[str] = None


@dataclass
class StepRecord:
    status: StepStatus = StepStatus.NOT_STARTED
    method: Optional[Method] = None
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        self.status = StepStatus(self.status)
        self.method = _enum(Method, self.method)


@dataclass
class SimulationRow:
    item: str  # what was simulated, e.g. "Stop stiffness against the target from R3"
    result: str  # as the CAD tool reported it, e.g. "within range"


@dataclass
class ParameterVersion:
    number: int  # 1, 2, ...: a save never changes an earlier version
    values: dict[str, str]  # parameter key -> value as typed
    note: Optional[str]
    saved_at: str
    basis: dict[str, str] = field(default_factory=dict)  # key -> a Basis value
    basis_notes: dict[str, str] = field(default_factory=dict)  # key -> e.g. "thickness by body weight"
    links: dict[str, list[str]] = field(default_factory=dict)  # key -> the requirement ids it serves
    by: Optional[str] = None  # who saved it, as written ("orthotist", "technician")

    def __post_init__(self) -> None:
        self.basis = {key: Basis(value).value for key, value in self.basis.items()}

    def same_as(self, other: "ParameterVersion") -> bool:
        return (self.values, self.basis, self.basis_notes, self.links) == (
            other.values, other.basis, other.basis_notes, other.links)


@dataclass
class OrthoticPlan:
    requirements: list[Requirement] = field(default_factory=list)
    options: list[DesignOption] = field(default_factory=list)
    chosen: Optional[str] = None  # the option id the orthotist chose, or FES_REFERRAL
    choice_reason: Optional[str] = None
    steps: dict[str, StepRecord] = field(default_factory=dict)  # Step value -> its record
    parameter_versions: list[ParameterVersion] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    fes: FesReferral = field(default_factory=FesReferral)
    simulation: list[SimulationRow] = field(default_factory=list)
    hot_spots: list[str] = field(default_factory=list)  # pressure hot spots, as entered
    relief_note: Optional[str] = None  # e.g. "Relief added at all three in v3 (R6)"
    # parameter key -> {"version": n, "at": time}: the orthotist approved the value it had in version n.
    approvals: dict[str, dict] = field(default_factory=dict)
    sent_to_manufacture_at: Optional[str] = None
    fit: FitRecord = field(default_factory=FitRecord)
    follow_up: FollowUp = field(default_factory=FollowUp)

    def __post_init__(self) -> None:
        wrong = [a.back_to for a in self.follow_up.alerts if a.back_to is not None and a.back_to not in BACK_TO]
        if wrong:
            raise PlanError(f"an alert loops back to one of {BACK_TO}, not {wrong}")

    # ---- Reading ----------------------------------------------------------

    def requirement(self, requirement_id: str) -> Optional[Requirement]:
        return next((r for r in self.requirements if r.id == requirement_id), None)

    def option(self, option_id: Optional[str]) -> Optional[DesignOption]:
        return next((o for o in self.options if o.id == option_id), None)

    def step(self, step: Step) -> StepRecord:
        return self.steps.get(step.value) or StepRecord()

    @property
    def current(self) -> Optional[ParameterVersion]:
        return self.parameter_versions[-1] if self.parameter_versions else None

    @property
    def parameters(self) -> dict[str, str]:
        """The latest saved parameter values ({} before the first save)."""
        return self.current.values if self.current else {}

    def approved(self, key: str) -> bool:
        """Whether the orthotist approved this parameter's current value (a later change undoes it)."""
        approval = self.approvals.get(key)
        if approval is None or key not in self.parameters:
            return False
        approved_in = self.parameter_versions[approval["version"] - 1]
        return approved_in.values.get(key) == self.parameters[key]

    def to_approve(self) -> list[str]:
        """The current parameters the orthotist hasn't approved yet, in PARAMETERS order."""
        return [key for key in PARAMETERS if key in self.parameters and not self.approved(key)]

    def next_requirement_id(self) -> str:
        return next_requirement_id(self.requirements)

    # ---- Changing (each checks before it changes anything) ----------------

    def set_requirements(self, requirements: list[Requirement], known_findings: set[str]) -> None:
        check_requirements(requirements, known_findings)
        ids = [r.id for r in requirements]
        self.requirements = requirements
        # Marks, part links, parameter links and conflicts to a requirement that is gone go with it.
        for option in self.options:
            option.marks = {req: mark for req, mark in option.marks.items() if req in ids}
            option.mark_notes = {req: note for req, note in option.mark_notes.items() if req in ids}
            for part in option.parts:
                part.requirements = [req for req in part.requirements if req in ids]
        self.conflicts = [c for c in self.conflicts if c.first in ids and c.second in ids]

    def set_conflicts(self, conflicts: list[Conflict]) -> None:
        check_conflicts(conflicts, self.requirements)
        self.conflicts = conflicts

    def set_options(self, options: list[DesignOption]) -> None:
        ids = [o.id for o in options]
        if len(ids) != len(set(ids)) or not set(ids) <= set(OPTION_IDS):
            raise PlanError(f"option ids must be distinct, from {OPTION_IDS}")
        known = {r.id for r in self.requirements}
        for option in options:
            if len(option.parts) > MAX_PARTS_PER_OPTION:
                raise PlanError(f"option {option.id}: more than {MAX_PARTS_PER_OPTION} parts")
            if len(option.costs) > MAX_LIST or len(option.checks) > MAX_LIST:
                raise PlanError(f"option {option.id}: more than {MAX_LIST} lines")
            linked = set(option.marks) | set(option.mark_notes) | {req for part in option.parts
                                                                    for req in part.requirements}
            if linked - known:
                raise PlanError(f"option {option.id}: not a requirement: {sorted(linked - known)}")
        before = self.option(self.chosen)
        self.options = options
        if self.chosen == FES_REFERRAL:
            return  # the referral isn't one of the options
        after = self.option(self.chosen)
        # The reason was given for that device and those parts: if the chosen option was
        # removed or became another device or other parts, the choice goes with it (the
        # review log keeps the choice as it was made). New marks or notes keep it.
        if before is None or after is None or _design(after) != _design(before):
            self.chosen, self.choice_reason = None, None

    def set_fes(self, referral: FesReferral) -> None:
        if len(referral.checks) > MAX_LIST:
            raise PlanError(f"more than {MAX_LIST} lines")
        self.fes = referral

    def choose(self, option_id: str, reason: str) -> None:
        if option_id != FES_REFERRAL and self.option(option_id) is None:
            raise PlanError(f"no option {option_id!r}")
        if not reason.strip():
            raise PlanError("a choice needs its reason")
        self.chosen, self.choice_reason = option_id, reason.strip()

    def set_steps(self, steps: dict[Step, StepRecord]) -> None:
        for step, record in steps.items():
            if record.method is not None and record.method not in STEP_METHODS[step]:
                raise PlanError(f"{step.value}: {record.method.value} is not one of its methods")
        self.steps = {step.value: record for step, record in steps.items()}

    def set_simulation(self, rows: list[SimulationRow], hot_spots: list[str], relief_note: Optional[str]) -> None:
        if len(rows) > MAX_LIST or len(hot_spots) > MAX_LIST:
            raise PlanError(f"more than {MAX_LIST} lines")
        self.simulation, self.hot_spots, self.relief_note = rows, hot_spots, relief_note

    def save_parameters(self, values: dict[str, str], note: Optional[str], basis: Optional[dict[str, str]] = None,
                        basis_notes: Optional[dict[str, str]] = None, links: Optional[dict[str, list[str]]] = None,
                        by: Optional[str] = None) -> ParameterVersion:
        """Keep the values as a new version. Values left empty are not kept; nothing new is not saved."""
        unknown = set(values) | set(basis or {}) | set(basis_notes or {}) | set(links or {})
        unknown -= set(PARAMETERS)
        if unknown:
            raise PlanError(f"not a design parameter: {sorted(unknown)}")
        values = {key: value.strip() for key, value in values.items() if value and value.strip()}
        keep = lambda d: {key: v for key, v in (d or {}).items() if key in values and v}  # noqa: E731
        requirement_ids = {r.id for r in self.requirements}
        links = {key: [rid for rid in ids if rid in requirement_ids] for key, ids in keep(links).items()}
        version = ParameterVersion(len(self.parameter_versions) + 1, values, (note or "").strip() or None, _now(),
                                   keep(basis), {k: v.strip() for k, v in keep(basis_notes).items() if v.strip()},
                                   {k: v for k, v in links.items() if v}, (by or "").strip() or None)
        if self.current is not None and version.same_as(self.current):
            raise PlanError("no change since the last version")
        if self.current is None and not values:
            raise PlanError("no change since the last version")
        self.parameter_versions.append(version)
        return version

    def approve(self, key: str) -> None:
        """The orthotist approves a parameter's current value."""
        if key not in self.parameters:
            raise PlanError(f"no current value for {key!r}")
        self.approvals[key] = {"version": self.current.number, "at": _now()}

    def send_to_manufacture(self) -> None:
        """Only with parameters saved and every one approved; the manufacture step is then in progress."""
        if not self.parameters or self.to_approve():
            raise PlanError("every parameter must be approved first")
        self.sent_to_manufacture_at = _now()
        record = self.step(Step.FABRICATE)
        if record.status in (StepStatus.NOT_STARTED, StepStatus.NOT_NEEDED):
            self.steps[Step.FABRICATE.value] = StepRecord(StepStatus.IN_PROGRESS, record.method, record.notes)

    # ---- Files --------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirements": [{"id": r.id, "text": r.text, "findings": list(r.findings),
                              "priority": r.priority.value if r.priority else None} for r in self.requirements],
            "options": [{"id": o.id, "device": o.device.value,
                         "parts": [{"part": p.part.value, "requirements": list(p.requirements), "note": p.note}
                                   for p in o.parts],
                         "marks": {req: mark.value for req, mark in o.marks.items()}, "notes": o.notes,
                         "summary": o.summary, "mark_notes": dict(o.mark_notes), "costs": list(o.costs),
                         "checks": list(o.checks), "stock": o.stock}
                        for o in self.options],
            "chosen": self.chosen,
            "choice_reason": self.choice_reason,
            "steps": {name: {"status": s.status.value, "method": s.method.value if s.method else None,
                             "notes": s.notes} for name, s in self.steps.items()},
            "parameter_versions": [{"number": v.number, "values": dict(v.values), "note": v.note,
                                    "saved_at": v.saved_at, "basis": dict(v.basis), "basis_notes": dict(v.basis_notes),
                                    "links": {k: list(ids) for k, ids in v.links.items()}, "by": v.by}
                                   for v in self.parameter_versions],
            "conflicts": [{"first": c.first, "second": c.second, "note": c.note} for c in self.conflicts],
            "fes": {"checks": list(self.fes.checks), "note": self.fes.note},
            "simulation": [{"item": r.item, "result": r.result} for r in self.simulation],
            "hot_spots": list(self.hot_spots),
            "relief_note": self.relief_note,
            "approvals": {key: dict(a) for key, a in self.approvals.items()},
            "sent_to_manufacture_at": self.sent_to_manufacture_at,
            "fit": self.fit.to_dict(),
            "follow_up": self.follow_up.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OrthoticPlan":
        """A saved plan; one saved before a key existed gets its default (case file version 3, log 7-8)."""
        return cls(
            requirements=[Requirement(**r) for r in data.get("requirements", [])],
            options=[DesignOption(**o) for o in data.get("options", [])],
            chosen=data.get("chosen"),
            choice_reason=data.get("choice_reason"),
            steps={name: StepRecord(**s) for name, s in data.get("steps", {}).items()},
            parameter_versions=[ParameterVersion(**v) for v in data.get("parameter_versions", [])],
            conflicts=[Conflict(**c) for c in data.get("conflicts", [])],
            fes=FesReferral(**(data.get("fes") or {})),
            simulation=[SimulationRow(**r) for r in data.get("simulation", [])],
            hot_spots=list(data.get("hot_spots", [])),
            relief_note=data.get("relief_note"),
            approvals={key: dict(a) for key, a in (data.get("approvals") or {}).items()},
            sent_to_manufacture_at=data.get("sent_to_manufacture_at"),
            fit=FitRecord.from_dict(data.get("fit")),
            follow_up=FollowUp.from_dict(data.get("follow_up")),
        )

    @classmethod
    def started_from(cls, case: OrthoticCase) -> "OrthoticPlan":
        """A new plan: the requirements written at intake become R1, R2, ... (no findings or priority yet)."""
        return cls(requirements=[Requirement(f"R{n}", text) for n, text in enumerate(case.requirements or [], 1)])


# ---- The case's findings a requirement can come from ------------------------
# Finding (shared/requirements.py): key "deviation.toe_drag", "exam.foot_posture", "functional_goals", ...; group
# "gait", "exam", "other" or "missing"; path None for a gait deviation.


# Recorded values a requirement may come from, by group (the gait deviations come first).
_EXAM_PATHS = ("exam.dorsiflexion_knee_extended_deg", "exam.dorsiflexion_knee_flexed_deg",
               "exam.plantarflexor_tone_grade", "exam.dorsiflexor_strength", "exam.knee_extensor_strength",
               "exam.knee_in_stance", "exam.foot_posture", "exam.protective_sensation", "exam.proprioception",
               "exam.skin_condition")
_OTHER_PATHS = ("functional_goals", "goal_participation", "goal_body_function", "walking.status",
                "walking.gait_speed_m_s", "walking.falls_last_6_months", "footwear", "donning", "body_weight_kg")
FINDING_PATHS = _EXAM_PATHS + _OTHER_PATHS


def case_findings(case: OrthoticCase) -> list[Finding]:
    """What the case recorded that a requirement can come from: gait deviations, exam values, goals.

    Only recorded values; a field left empty or "unknown" is an information gap
    (module 1). missing_findings() lists those, for a requirement that waits on one.
    """
    findings = [Finding(f"deviation.{d.value}", "gait", None, d) for d in case.walking.deviations or []]
    for group, paths in (("exam", _EXAM_PATHS), ("other", _OTHER_PATHS)):
        for path in paths:
            value = value_at(case, path)
            if recorded(value):
                findings.append(Finding(path, group, path, value))
    return findings


def missing_findings(case: OrthoticCase) -> list[Finding]:
    """The values a requirement can come from that aren't recorded yet (module 2: "provisional")."""
    return [Finding(path, "missing", path, None) for path in FINDING_PATHS if not recorded(value_at(case, path))]


def linkable(case: OrthoticCase) -> set[str]:
    """Every key a requirement may name: the recorded deviations and every value, recorded or not."""
    return {f.key for f in case_findings(case)} | set(FINDING_PATHS)


def waiting_on(requirement: Requirement, case: OrthoticCase) -> list[str]:
    """The values the requirement names that aren't recorded yet: while any is, it is provisional."""
    return [key for key in requirement.findings if key in FINDING_PATHS and not recorded(value_at(case, key))]


# The class a saved plan is read back with (shared/store.py, through shared/domains.py).
PLAN = OrthoticPlan
