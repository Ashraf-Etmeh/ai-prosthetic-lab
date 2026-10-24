"""The orthotics case: the shared core (shared/case_schema.py) plus the condition, walking, the exam
and the device history. Use case 03, stroke AFO first (added 2026-10-22).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, Optional

from shared.case_schema import CaseCore, PriorDevice, Side, YesNoUnknown, check_number, register_case, to_enum

# PROPOSAL, awaiting the owner's and an orthotist's review (CLAUDE.md: the
# orthotic intake fields and which are critical come from the owner; the
# owner chose on 2026-10-22 to build Claude's proposal as a draft). The fields
# follow the stroke-AFO minimum data set proposed in the independent blueprint
# (section 7) and the discussion of 2026-10-21: what the case needs before an
# orthotist weighs an ankle-foot orthosis or FES. The case records findings
# only; what the orthosis must do (`requirements`) is written by the orthotist.


class OrthoticCondition(str, Enum):
    STROKE = "stroke"  # the first area (owner's decision, 2026-10-16); others come later


class WalkingStatus(str, Enum):
    NON_AMBULATORY = "non_ambulatory"
    WITH_ASSISTANCE = "with_assistance"  # walks with another person's help
    INDEPENDENT_WITH_AID = "independent_with_aid"  # alone, with a cane, crutch or walker
    INDEPENDENT = "independent"  # alone, no aid
    UNKNOWN = "unknown"


class KneeInStance(str, Enum):
    STABLE = "stable"
    HYPEREXTENDS = "hyperextends"
    BUCKLES = "buckles"
    UNKNOWN = "unknown"


class SensationStatus(str, Enum):
    INTACT = "intact"
    REDUCED = "reduced"
    ABSENT = "absent"
    UNKNOWN = "unknown"


class ToneScale(str, Enum):
    """The scale a tone grade was measured with: a grade means little without it."""

    MODIFIED_ASHWORTH = "modified_ashworth"
    MODIFIED_TARDIEU = "modified_tardieu"
    OTHER = "other"


class DonningAbility(str, Enum):
    INDEPENDENT = "independent"
    NEEDS_HELP = "needs_help"
    UNKNOWN = "unknown"


class GaitDeviation(str, Enum):
    """Deviations an orthotist can tick after observing gait, each in its gait phase."""

    FOOT_FLAT_CONTACT = "foot_flat_contact"  # initial contact
    KNEE_HYPEREXTENSION = "knee_hyperextension"  # mid-stance
    KNEE_BUCKLING = "knee_buckling"  # mid-stance
    NO_HEEL_RISE = "no_heel_rise"  # terminal stance
    REDUCED_PUSH_OFF = "reduced_push_off"  # pre-swing
    TOE_DRAG = "toe_drag"  # swing (foot drop)
    CIRCUMDUCTION = "circumduction"  # swing: hip hitching or circumduction, a compensation

    @property
    def phase(self) -> str:
        return _DEVIATION_PHASES[self]


_DEVIATION_PHASES = {
    GaitDeviation.FOOT_FLAT_CONTACT: "initial_contact",
    GaitDeviation.KNEE_HYPEREXTENSION: "mid_stance",
    GaitDeviation.KNEE_BUCKLING: "mid_stance",
    GaitDeviation.NO_HEEL_RISE: "terminal_stance",
    GaitDeviation.REDUCED_PUSH_OFF: "pre_swing",
    GaitDeviation.TOE_DRAG: "swing",
    GaitDeviation.CIRCUMDUCTION: "swing",
}
# The phases of the gait cycle, in order, for showing deviations phase by phase.
GAIT_PHASES = ("initial_contact", "loading_response", "mid_stance", "terminal_stance", "pre_swing", "swing")
# Ankle angles are signed (dorsiflexion positive, plantarflexion negative): -5 means
# the ankle stops 5 degrees short of neutral. Anything outside this is a typing error.
MAX_ANKLE_DEGREES = 90
# The values whose "how it was measured" the orthotist records (module 1's exam table,
# from the design canvas: "Every value keeps how it was measured"). The tone grade has its
# scale and notes, and the gait speed its test, as fields of their own.
MEASURED_PATHS = (
    "exam.dorsiflexion_knee_extended_deg", "exam.dorsiflexion_knee_flexed_deg", "exam.dorsiflexor_strength",
    "exam.knee_extensor_strength", "exam.knee_in_stance", "exam.foot_posture", "exam.protective_sensation",
    "exam.proprioception", "exam.skin_condition", "exam.ulcer_infection_or_poor_blood_supply", "walking.status",
    "walking.falls_last_6_months", "footwear", "donning", "prior_orthoses",
)
MAX_MEASURED_HOW = 200  # characters


@dataclass
class Walking:
    status: Optional[WalkingStatus] = None
    walking_aid: Optional[str] = None  # e.g. "quad cane"
    gait_speed_m_s: Optional[float] = None
    gait_speed_test: Optional[str] = None  # which test, e.g. "10-metre walk test"; needed with a speed
    falls_last_6_months: Optional[int] = None
    # None = gait not observed; [] = observed, no deviation from the list.
    deviations: Optional[list[GaitDeviation]] = None
    other_deviations: Optional[str] = None

    def __post_init__(self) -> None:
        self.status = to_enum(WalkingStatus, self.status)
        if self.deviations is not None:
            self.deviations = [GaitDeviation(d) for d in self.deviations]
        check_number("gait_speed_m_s", self.gait_speed_m_s)
        check_number("falls_last_6_months", self.falls_last_6_months)
        if self.gait_speed_m_s is not None and not (self.gait_speed_test or "").strip():
            raise ValueError("gait_speed_test must name the test a gait speed was measured with")


@dataclass
class OrthoticExam:
    dorsiflexion_knee_extended_deg: Optional[float] = None  # passive, signed
    dorsiflexion_knee_flexed_deg: Optional[float] = None  # passive, signed
    plantarflexor_tone_scale: Optional[ToneScale] = None
    plantarflexor_tone_grade: Optional[str] = None  # as the scale writes it, e.g. "1+"
    plantarflexor_tone_notes: Optional[str] = None  # position, muscle, rater
    dorsiflexor_strength: Optional[str] = None  # e.g. "MRC 2/5"
    knee_extensor_strength: Optional[str] = None
    knee_in_stance: Optional[KneeInStance] = None
    foot_posture: Optional[str] = None  # e.g. "equinovarus, flexible"
    protective_sensation: Optional[SensationStatus] = None
    proprioception: Optional[SensationStatus] = None
    skin_condition: Optional[str] = None
    # The first of the design map's draft hard stops (orthotics/hard_stops.py, awaiting the owner); never a gap.
    ulcer_infection_or_poor_blood_supply: Optional[YesNoUnknown] = None

    def __post_init__(self) -> None:
        self.plantarflexor_tone_scale = to_enum(ToneScale, self.plantarflexor_tone_scale)
        self.knee_in_stance = to_enum(KneeInStance, self.knee_in_stance)
        self.protective_sensation = to_enum(SensationStatus, self.protective_sensation)
        self.proprioception = to_enum(SensationStatus, self.proprioception)
        self.ulcer_infection_or_poor_blood_supply = to_enum(YesNoUnknown, self.ulcer_infection_or_poor_blood_supply)
        for name in ("dorsiflexion_knee_extended_deg", "dorsiflexion_knee_flexed_deg"):
            _check_angle(name, getattr(self, name))
        if self.plantarflexor_tone_grade and self.plantarflexor_tone_scale is None:
            raise ValueError("plantarflexor_tone_grade needs plantarflexor_tone_scale: name the scale")


@register_case
@dataclass
class OrthoticCase(CaseCore):
    """An orthotics case: the shared core plus the condition, walking, the exam and the device history."""

    domain: ClassVar[str] = "orthotics"

    # Required at creation
    condition: OrthoticCondition
    side: Side  # the affected side

    months_since_onset: Optional[float] = None
    # Goals by ICF level (the design's "Goals, by ICF level"): functional_goals is the
    # activity goal (a gap field since 2026-10-22); the other two are never gaps.
    functional_goals: Optional[str] = None
    goal_participation: Optional[str] = None
    goal_body_function: Optional[str] = None
    walking: Walking = field(default_factory=Walking)
    exam: OrthoticExam = field(default_factory=OrthoticExam)
    # How each value was measured, by its path in MEASURED_PATHS, as the orthotist wrote it.
    measured_how: dict[str, str] = field(default_factory=dict)
    footwear: Optional[str] = None  # e.g. "closed trainers, heel 1 cm"
    donning: Optional[DonningAbility] = None  # putting an orthosis on
    # None = not asked; [] = asked, no orthosis or FES used before.
    prior_orthoses: Optional[list[PriorDevice]] = None
    # Asked only if FES is discussed; never listed as missing information.
    implanted_electronic_device: Optional[YesNoUnknown] = None
    # What the orthosis must do, written by the orthotist (module 2), one per item.
    requirements: Optional[list[str]] = None

    def __post_init__(self) -> None:
        super().__post_init__()
        self.condition = OrthoticCondition(self.condition)
        self.side = Side(self.side)
        self.donning = to_enum(DonningAbility, self.donning)
        self.implanted_electronic_device = to_enum(YesNoUnknown, self.implanted_electronic_device)
        check_number("months_since_onset", self.months_since_onset)
        unknown = set(self.measured_how) - set(MEASURED_PATHS)
        if unknown:
            raise ValueError(f"measured_how: not a measured value: {sorted(unknown)}")
        self.measured_how = {path: text.strip() for path, text in self.measured_how.items() if text and text.strip()}
        if any(len(text) > MAX_MEASURED_HOW for text in self.measured_how.values()):
            raise ValueError(f"measured_how: at most {MAX_MEASURED_HOW} characters each")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OrthoticCase":
        data = dict(data)
        data["walking"] = Walking(**(data.get("walking") or {}))
        data["exam"] = OrthoticExam(**(data.get("exam") or {}))
        data["measured_how"] = dict(data.get("measured_how") or {})  # none before 2026-10-23
        if data.get("prior_orthoses") is not None:
            data["prior_orthoses"] = [PriorDevice(**d) for d in data["prior_orthoses"]]
        for name in ("comorbidities", "requirements"):
            if data.get(name) is not None:
                data[name] = list(data[name])
        return cls(**data)

    @property
    def is_lower_limb(self) -> bool:
        return True  # stroke AFO: an ankle-foot orthosis


def _check_angle(name: str, value: Optional[float]) -> None:
    if value is None:
        return
    if not math.isfinite(value) or abs(value) > MAX_ANKLE_DEGREES:
        raise ValueError(f"{name} must be between -{MAX_ANKLE_DEGREES} and {MAX_ANKLE_DEGREES}, got {value!r}")
