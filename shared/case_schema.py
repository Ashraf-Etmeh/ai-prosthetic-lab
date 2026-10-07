"""Case-object schema for AI Prosthetic Lab (v1 prototype).

A Case holds the intake data for one prosthetics evaluation. It is the object
passed between intake -> knowledge -> reasoning -> review.

Conventions:
- A field set to None means "not recorded at intake". The reasoning layer
  treats None as a potential information gap. Fields that were asked about
  but whose answer was not known use the explicit UNKNOWN enum value instead,
  so "never asked" and "asked, answer unknown" stay distinct.
- No direct identifiers (name, DOB, address, record numbers). Cases are keyed
  by an opaque case_id. The prototype is for fake/test data only.
- The schema describes intake facts only. It holds no treatment or component
  selection; that decision belongs to the specialist.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


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


class Side(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    BILATERAL = "bilateral"


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
        self.wound_status = _to_enum(WoundStatus, self.wound_status)
        self.volume_stability = _to_enum(VolumeStability, self.volume_stability)


@dataclass
class ActivityProfile:
    k_level: Optional[ActivityLevel] = None  # lower limb only
    description: Optional[str] = None  # current daily activity in the patient's terms
    functional_goals: Optional[str] = None  # what the patient wants to be able to do

    def __post_init__(self) -> None:
        self.k_level = _to_enum(ActivityLevel, self.k_level)


@dataclass
class PriorDevice:
    device_description: str  # free text, e.g. "transtibial PTB socket, SACH foot"
    years_used: Optional[float] = None
    currently_using: Optional[bool] = None
    issues: Optional[str] = None  # fit, comfort, skin, mechanical problems


@dataclass
class Case:
    # Required at creation
    amputation_level: AmputationLevel
    side: Side

    # Identity / bookkeeping
    case_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    # Demographics (minimal, non-identifying)
    age_years: Optional[int] = None
    body_weight_kg: Optional[float] = None

    # Amputation history
    etiology: Optional[Etiology] = None
    months_since_amputation: Optional[float] = None

    # Core evaluation inputs
    residual_limb: ResidualLimb = field(default_factory=ResidualLimb)
    activity: ActivityProfile = field(default_factory=ActivityProfile)
    # None = device history not asked; [] = asked, no prior devices.
    prior_devices: Optional[list[PriorDevice]] = None

    # Relevant health context
    comorbidities: Optional[list[str]] = None  # [] = asked, none reported
    contralateral_limb_status: Optional[str] = None  # lower limb: other leg's condition
    cognitive_status: Optional[str] = None  # ability to learn donning/doffing, device care

    intake_notes: Optional[str] = None

    # ---- Validation ----------------------------------------------------

    def __post_init__(self) -> None:
        # Accept enum members or their string values; reject anything else.
        self.amputation_level = AmputationLevel(self.amputation_level)
        self.side = Side(self.side)
        self.etiology = _to_enum(Etiology, self.etiology)

        _check_number("age_years", self.age_years)
        _check_number("body_weight_kg", self.body_weight_kg, positive=True)
        _check_number("months_since_amputation", self.months_since_amputation)

    # ---- Serialization -------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return _enums_to_values(asdict(self))

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

    def unrecorded_fields(self) -> list[str]:
        """Dotted paths of fields left as None (not recorded at intake).

        Fields that don't apply to this case are skipped (e.g. K-level and
        contralateral limb status for upper-limb cases). This only reports
        what is empty. Whether a field matters for the evaluation is decided
        in the reasoning layer against the protocols.
        """
        skip = self._not_applicable()
        return [path for path, value in self._leaf_values() if value is None and path not in skip]

    def unknown_fields(self) -> list[str]:
        """Dotted paths of fields recorded as UNKNOWN (asked, answer not known).

        Skips fields that don't apply to this case, like unrecorded_fields().
        """
        skip = self._not_applicable()
        return [
            path
            for path, value in self._leaf_values()
            if isinstance(value, Enum) and value.value == "unknown" and path not in skip
        ]

    def _not_applicable(self) -> set[str]:
        if self.is_lower_limb:
            return set()
        return {"activity.k_level", "contralateral_limb_status"}

    def _leaf_values(self):
        """Yield (dotted path, value) for every field, opening the nested sections."""
        for f in fields(self):
            value = getattr(self, f.name)
            if isinstance(value, (ResidualLimb, ActivityProfile)):
                for sub in fields(value):
                    yield f"{f.name}.{sub.name}", getattr(value, sub.name)
            else:
                yield f.name, value


def _to_enum(enum_cls: type[Enum], value: Any) -> Any:
    return None if value is None else enum_cls(value)


def _check_number(name: str, value: Optional[float], positive: bool = False) -> None:
    if value is None:
        return
    if not math.isfinite(value) or value < 0 or (positive and value == 0):
        rule = "greater than 0" if positive else "0 or greater"
        raise ValueError(f"{name} must be {rule}, got {value!r}")


def _enums_to_values(obj: Any) -> Any:
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {k: _enums_to_values(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_enums_to_values(v) for v in obj]
    return obj
