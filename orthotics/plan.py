"""The orthotist's work on an orthotic case after its analysis: modules 2-4 (added 2026-10-23).

The brief's orthotics capabilities, after "functional case analysis" (module 1:
the intake form and the review page):
- Module 2, requirements: what the orthosis must do, in the orthotist's words,
  each tied to the case findings it comes from (a gait deviation, an exam
  value, a goal) and given a priority by the orthotist.
- Module 3, design options ("choosing and designing orthotic devices" and
  "linking the case to components and materials"): up to three options, each a
  device type with its materials and parts, each part tied to the requirements
  it serves, the orthotist's own marks of which requirements the option
  addresses, and their notes. Shown side by side in the order entered, never
  ranked; the orthotist chooses one and gives the reason (review log).
- Module 4, digital design ("supporting the digital design workflow"): the
  steps from capture to release with their status and method, and the design
  parameters as the orthotist sets them, every save kept as a new version.

Nothing here is written, chosen or suggested by code or the AI: every value is
the orthotist's. The vocabularies below (device types, parts, steps, methods,
parameters) are a PROPOSAL awaiting the owner and an orthotist, like the
intake fields; only their fixed words are ever searched (orthotics/sources.py),
never what the orthotist typed.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from shared.case_schema import OrthoticCase


class Priority(str, Enum):
    MUST = "must"
    SHOULD = "should"
    NICE = "nice"


class Mark(str, Enum):
    """The orthotist's mark: does this option address that requirement?"""

    YES = "yes"
    PARTLY = "partly"
    NO = "no"


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
    """The design and fabrication workflow, in order."""

    CAPTURE = "capture"
    RECTIFY = "rectify"
    PARAMETERS = "parameters"
    FABRICATE = "fabricate"
    RELEASE = "release"


class StepStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    NOT_NEEDED = "not_needed"


class Method(str, Enum):
    PLASTER_CAST = "plaster_cast"
    SCAN_3D = "scan_3d"
    MEASUREMENTS = "measurements"
    PLASTER_MODEL = "plaster_model"
    CAD = "cad"
    THERMOFORMING = "thermoforming"
    PRINTING_3D = "printing_3d"
    PREFABRICATED = "prefabricated"


# The methods a step can be done with (a step with none has no method to choose).
STEP_METHODS: dict[Step, tuple[Method, ...]] = {
    Step.CAPTURE: (Method.PLASTER_CAST, Method.SCAN_3D, Method.MEASUREMENTS),
    Step.RECTIFY: (Method.PLASTER_MODEL, Method.CAD),
    Step.PARAMETERS: (),
    Step.FABRICATE: (Method.THERMOFORMING, Method.PRINTING_3D, Method.PREFABRICATED),
    Step.RELEASE: (),
}

# Design parameters the orthotist records, in the order shown. Values are as typed.
PARAMETERS = ("ankle_angle", "plantarflexion_stop", "trim_lines", "footplate", "shell", "lining", "closure",
              "joints", "heel_wedge")

OPTION_IDS = ("A", "B", "C")
MAX_PARTS_PER_OPTION = 6
MAX_TEXT = 500  # characters in one typed value (a requirement, a note, a parameter)


class PlanError(ValueError):
    """A plan that can't be kept as it is (raised before anything is saved)."""


def _enum(cls, value):
    return None if value is None else cls(value)


def _design(option: "DesignOption") -> tuple:
    """What an option is: its device and its parts (not the orthotist's marks or notes on it)."""
    return option.device, sorted(part.part.value for part in option.parts)


@dataclass
class Requirement:
    id: str  # "R1", "R2", ...: kept when the text changes
    text: str  # the orthotist's words
    findings: list[str] = field(default_factory=list)  # case_findings() keys it comes from
    priority: Optional[Priority] = None

    def __post_init__(self) -> None:
        self.priority = _enum(Priority, self.priority)


@dataclass
class OptionPart:
    part: Part
    requirements: list[str] = field(default_factory=list)  # the requirement ids it serves

    def __post_init__(self) -> None:
        self.part = Part(self.part)


@dataclass
class DesignOption:
    id: str  # "A", "B" or "C": the order the orthotist entered them, never a rank
    device: DeviceType
    parts: list[OptionPart] = field(default_factory=list)
    marks: dict[str, Mark] = field(default_factory=dict)  # requirement id -> the orthotist's mark
    notes: Optional[str] = None  # costs to the patient, checks at fitting: the orthotist's words

    def __post_init__(self) -> None:
        self.device = DeviceType(self.device)
        self.parts = [p if isinstance(p, OptionPart) else OptionPart(**p) for p in self.parts]
        self.marks = {req: Mark(mark) for req, mark in self.marks.items()}

    def unaddressed(self, requirements: list[Requirement]) -> list[Requirement]:
        """The Must requirements the orthotist marked this option as not addressing."""
        return [r for r in requirements if r.priority is Priority.MUST and self.marks.get(r.id) is Mark.NO]


@dataclass
class StepRecord:
    status: StepStatus = StepStatus.NOT_STARTED
    method: Optional[Method] = None
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        self.status = StepStatus(self.status)
        self.method = _enum(Method, self.method)


@dataclass
class ParameterVersion:
    number: int  # 1, 2, ...: a save never changes an earlier version
    values: dict[str, str]  # parameter key -> value as typed
    note: Optional[str]
    saved_at: str


@dataclass
class OrthoticPlan:
    requirements: list[Requirement] = field(default_factory=list)
    options: list[DesignOption] = field(default_factory=list)
    chosen: Optional[str] = None  # the option id the orthotist chose
    choice_reason: Optional[str] = None
    steps: dict[str, StepRecord] = field(default_factory=dict)  # Step value -> its record
    parameter_versions: list[ParameterVersion] = field(default_factory=list)

    # ---- Reading ----------------------------------------------------------

    def requirement(self, requirement_id: str) -> Optional[Requirement]:
        return next((r for r in self.requirements if r.id == requirement_id), None)

    def option(self, option_id: Optional[str]) -> Optional[DesignOption]:
        return next((o for o in self.options if o.id == option_id), None)

    def step(self, step: Step) -> StepRecord:
        return self.steps.get(step.value) or StepRecord()

    @property
    def parameters(self) -> dict[str, str]:
        """The latest saved parameter values ({} before the first save)."""
        return self.parameter_versions[-1].values if self.parameter_versions else {}

    def next_requirement_id(self) -> str:
        numbers = [int(r.id[1:]) for r in self.requirements if r.id[1:].isdigit()]
        return f"R{max(numbers, default=0) + 1}"

    # ---- Changing (each checks before it changes anything) ----------------

    def set_requirements(self, requirements: list[Requirement], known_findings: set[str]) -> None:
        ids = [r.id for r in requirements]
        if len(ids) != len(set(ids)):
            raise PlanError("repeated requirement id")
        for r in requirements:
            if not r.text.strip():
                raise PlanError("a requirement without text")
            unknown = set(r.findings) - known_findings
            if unknown:
                raise PlanError(f"{r.id}: not a finding of this case: {sorted(unknown)}")
        self.requirements = requirements
        # Marks and part links to a requirement that is gone go with it.
        for option in self.options:
            option.marks = {req: mark for req, mark in option.marks.items() if req in ids}
            for part in option.parts:
                part.requirements = [req for req in part.requirements if req in ids]

    def set_options(self, options: list[DesignOption]) -> None:
        ids = [o.id for o in options]
        if len(ids) != len(set(ids)) or not set(ids) <= set(OPTION_IDS):
            raise PlanError(f"option ids must be distinct, from {OPTION_IDS}")
        known = {r.id for r in self.requirements}
        for option in options:
            if len(option.parts) > MAX_PARTS_PER_OPTION:
                raise PlanError(f"option {option.id}: more than {MAX_PARTS_PER_OPTION} parts")
            linked = set(option.marks) | {req for part in option.parts for req in part.requirements}
            if linked - known:
                raise PlanError(f"option {option.id}: not a requirement: {sorted(linked - known)}")
        before = self.option(self.chosen)
        self.options = options
        after = self.option(self.chosen)
        # The reason was given for that device and those parts: if the chosen option was
        # removed or became another device or other parts, the choice goes with it (the
        # review log keeps the choice as it was made). New marks or notes keep it.
        if before is None or after is None or _design(after) != _design(before):
            self.chosen, self.choice_reason = None, None

    def choose(self, option_id: str, reason: str) -> None:
        if self.option(option_id) is None:
            raise PlanError(f"no option {option_id!r}")
        if not reason.strip():
            raise PlanError("a choice needs its reason")
        self.chosen, self.choice_reason = option_id, reason.strip()

    def set_steps(self, steps: dict[Step, StepRecord]) -> None:
        for step, record in steps.items():
            if record.method is not None and record.method not in STEP_METHODS[step]:
                raise PlanError(f"{step.value}: {record.method.value} is not one of its methods")
        self.steps = {step.value: record for step, record in steps.items()}

    def save_parameters(self, values: dict[str, str], note: Optional[str]) -> ParameterVersion:
        """Keep the values as a new version. Values left empty are not kept; nothing new is not saved."""
        unknown = set(values) - set(PARAMETERS)
        if unknown:
            raise PlanError(f"not a design parameter: {sorted(unknown)}")
        values = {key: value.strip() for key, value in values.items() if value and value.strip()}
        if values == self.parameters:
            raise PlanError("no change since the last version")
        version = ParameterVersion(len(self.parameter_versions) + 1, values, (note or "").strip() or None,
                                   datetime.now(timezone.utc).isoformat(timespec="seconds"))
        self.parameter_versions.append(version)
        return version

    # ---- Files --------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirements": [{"id": r.id, "text": r.text, "findings": list(r.findings),
                              "priority": r.priority.value if r.priority else None} for r in self.requirements],
            "options": [{"id": o.id, "device": o.device.value,
                         "parts": [{"part": p.part.value, "requirements": list(p.requirements)} for p in o.parts],
                         "marks": {req: mark.value for req, mark in o.marks.items()}, "notes": o.notes}
                        for o in self.options],
            "chosen": self.chosen,
            "choice_reason": self.choice_reason,
            "steps": {name: {"status": s.status.value, "method": s.method.value if s.method else None,
                             "notes": s.notes} for name, s in self.steps.items()},
            "parameter_versions": [{"number": v.number, "values": dict(v.values), "note": v.note,
                                    "saved_at": v.saved_at} for v in self.parameter_versions],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OrthoticPlan":
        return cls(
            requirements=[Requirement(**r) for r in data.get("requirements", [])],
            options=[DesignOption(**o) for o in data.get("options", [])],
            chosen=data.get("chosen"),
            choice_reason=data.get("choice_reason"),
            steps={name: StepRecord(**s) for name, s in data.get("steps", {}).items()},
            parameter_versions=[ParameterVersion(**v) for v in data.get("parameter_versions", [])],
        )

    @classmethod
    def started_from(cls, case: OrthoticCase) -> "OrthoticPlan":
        """A new plan: the requirements written at intake become R1, R2, ... (no findings or priority yet)."""
        return cls(requirements=[Requirement(f"R{n}", text) for n, text in enumerate(case.requirements or [], 1)])


# ---- The case's findings a requirement can come from ------------------------


@dataclass(frozen=True)
class Finding:
    key: str  # "deviation.toe_drag", "exam.foot_posture", "functional_goals", ...
    group: str  # "gait", "exam" or "other": how the requirements page groups them
    path: Optional[str]  # the field path whose label names it (None: a gait deviation)
    value: Any  # as recorded: a GaitDeviation, an enum, a number or text


# Recorded values a requirement may come from, by group (the gait deviations come first).
_EXAM_PATHS = ("exam.dorsiflexion_knee_extended_deg", "exam.dorsiflexion_knee_flexed_deg",
               "exam.plantarflexor_tone_grade", "exam.dorsiflexor_strength", "exam.knee_extensor_strength",
               "exam.knee_in_stance", "exam.foot_posture", "exam.protective_sensation", "exam.proprioception",
               "exam.skin_condition")
_OTHER_PATHS = ("functional_goals", "walking.status", "walking.gait_speed_m_s", "walking.falls_last_6_months",
                "footwear", "donning", "body_weight_kg")


def _value_at(case: OrthoticCase, path: str):
    value = case
    for name in path.split("."):
        value = getattr(value, name)
    return value


def case_findings(case: OrthoticCase) -> list[Finding]:
    """What the case recorded that a requirement can come from: gait deviations, exam values, goals.

    Only recorded values: a field left empty or "unknown" is an information
    gap (module 1), not a finding.
    """
    findings = [Finding(f"deviation.{d.value}", "gait", None, d) for d in case.walking.deviations or []]
    for group, paths in (("exam", _EXAM_PATHS), ("other", _OTHER_PATHS)):
        for path in paths:
            value = _value_at(case, path)
            if value is None or getattr(value, "value", None) == "unknown":
                continue
            findings.append(Finding(path, group, path, value))
    return findings
