"""The prosthetics case: the shared core (shared/case_schema.py) plus the amputation and the prosthesis.

Use cases 01 and 02. `Case` keeps the name it had before the domains were split
(2026-10-17); its dicts carry no "domain" (a dict without one is a prosthetics case).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, Optional

from shared.case_schema import CaseCore, PriorDevice, Side, check_number, register_case, to_enum


class AmputationLevel(str, Enum):
    # Lower limb
    PARTIAL_FOOT = "partial_foot"
    SYME = "syme"
    TRANSTIBIAL = "transtibial"
    KNEE_DISARTICULATION = "knee_disarticulation"
    TRANSFEMORAL = "transfemoral"
    HIP_DISARTICULATION = "hip_disarticulation"
    # Upper limb
    PARTIAL_HAND = "partial_hand"
    WRIST_DISARTICULATION = "wrist_disarticulation"
    TRANSRADIAL = "transradial"
    ELBOW_DISARTICULATION = "elbow_disarticulation"
    TRANSHUMERAL = "transhumeral"
    SHOULDER_DISARTICULATION = "shoulder_disarticulation"

    @property
    def is_lower_limb(self) -> bool:
        return self in _LOWER_LIMB_LEVELS


_LOWER_LIMB_LEVELS = {
    AmputationLevel.PARTIAL_FOOT,
    AmputationLevel.SYME,
    AmputationLevel.TRANSTIBIAL,
    AmputationLevel.KNEE_DISARTICULATION,
    AmputationLevel.TRANSFEMORAL,
    AmputationLevel.HIP_DISARTICULATION,
}


class Etiology(str, Enum):
    VASCULAR = "vascular"  # incl. diabetes-related
    TRAUMA = "trauma"
    ONCOLOGIC = "oncologic"
    INFECTION = "infection"
    CONGENITAL = "congenital"
    OTHER = "other"
    UNKNOWN = "unknown"


class ActivityLevel(str, Enum):
    """Medicare Functional Classification Level (K-level).

    Used for lower-limb cases. Upper-limb cases rely on
    ActivityProfile.description and functional goals instead.
    """

    K0 = "K0"  # no ability/potential to ambulate or transfer safely
    K1 = "K1"  # household ambulator, fixed cadence
    K2 = "K2"  # limited community ambulator, low-level barriers
    K3 = "K3"  # community ambulator, variable cadence
    K4 = "K4"  # exceeds basic ambulation (high impact / athletic)
    UNKNOWN = "unknown"


class WoundStatus(str, Enum):
    HEALED = "healed"
    HEALING = "healing"
    OPEN = "open"
    UNKNOWN = "unknown"


class VolumeStability(str, Enum):
    STABLE = "stable"
    FLUCTUATING = "fluctuating"
    UNKNOWN = "unknown"


@dataclass
class ResidualLimb:
    wound_status: Optional[WoundStatus] = None
    volume_stability: Optional[VolumeStability] = None
    skin_condition: Optional[str] = None  # e.g. grafts, scarring, adherent scar
    length_description: Optional[str] = None  # e.g. "short", "mid-length", or cm
    pain: Optional[str] = None  # residual-limb and/or phantom pain, free text
    sensation: Optional[str] = None  # e.g. intact, reduced, neuropathic
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        self.wound_status = to_enum(WoundStatus, self.wound_status)
        self.volume_stability = to_enum(VolumeStability, self.volume_stability)


@dataclass
class ActivityProfile:
    k_level: Optional[ActivityLevel] = None  # lower limb only
    description: Optional[str] = None  # current daily activity in the patient's terms
    functional_goals: Optional[str] = None  # what the patient wants to be able to do

    def __post_init__(self) -> None:
        self.k_level = to_enum(ActivityLevel, self.k_level)


@register_case
@dataclass
class Case(CaseCore):
    """A prosthetics case: the shared core plus the amputation and the prosthesis."""

    domain: ClassVar[str] = "prosthetics"

    # Required at creation
    amputation_level: AmputationLevel
    side: Side

    # Amputation history
    etiology: Optional[Etiology] = None
    months_since_amputation: Optional[float] = None

    # Core evaluation inputs
    residual_limb: ResidualLimb = field(default_factory=ResidualLimb)
    activity: ActivityProfile = field(default_factory=ActivityProfile)
    # None = device history not asked; [] = asked, no prior devices.
    prior_devices: Optional[list[PriorDevice]] = None

    contralateral_limb_status: Optional[str] = None  # lower limb: other leg's condition

    # ---- Validation ----------------------------------------------------

    def __post_init__(self) -> None:
        super().__post_init__()
        # Accept enum members or their string values; reject anything else.
        self.amputation_level = AmputationLevel(self.amputation_level)
        self.side = Side(self.side)
        self.etiology = to_enum(Etiology, self.etiology)

        check_number("months_since_amputation", self.months_since_amputation)

    # ---- Serialization -------------------------------------------------

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Case":
        # Enum strings are converted by each class's __post_init__, so only
        # the nested objects need rebuilding here.
        data = dict(data)
        data["residual_limb"] = ResidualLimb(**(data.get("residual_limb") or {}))
        data["activity"] = ActivityProfile(**(data.get("activity") or {}))
        if data.get("prior_devices") is not None:
            data["prior_devices"] = [PriorDevice(**d) for d in data["prior_devices"]]
        if data.get("comorbidities") is not None:
            data["comorbidities"] = list(data["comorbidities"])
        return cls(**data)

    # ---- Helpers for the reasoning layer -------------------------------

    @property
    def is_lower_limb(self) -> bool:
        return self.amputation_level.is_lower_limb

    def _not_applicable(self) -> set[str]:
        if self.is_lower_limb:
            return set()
        return {"activity.k_level", "contralateral_limb_status"}
