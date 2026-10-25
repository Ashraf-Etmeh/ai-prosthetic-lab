"""Module 5, fit, tune and train (added 2026-10-23, from the "Orthotics Module Design" canvas).

The brief's "understanding how the device relates to performance" and "linking the
device to functional training": what the orthotist checked at delivery, how the
orthosis was tuned and what they saw, the walking measures before and after, the
training plan as the physiotherapist set it, and the patient leaflet.

Every value is entered by the orthotist or the physiotherapist and kept as written.
The tool writes none of it: the leaflet is the orthotist's text (in Arabic and
English, checked by an Arabic-reading orthotist before any patient sees it), and the
rows it offers to start from come from what the orthotist wrote earlier (the
chosen option's checks at fitting, the requirements) or the intake (the gait speed
and the deviations recorded), never from the code.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from shared.dates import check_date


@dataclass
class CheckItem:
    text: str  # what was checked, in the orthotist's words
    done: bool = False
    note: Optional[str] = None  # e.g. "needs practice"


@dataclass
class TuningRow:
    step: str  # "Delivery", "Tune 1", ...
    change: str  # e.g. "5 mm heel wedge"
    seen: Optional[str] = None  # what the orthotist saw


@dataclass
class BeforeAfter:
    measure: str  # e.g. "Gait speed, 10-metre walk"
    before: Optional[str] = None
    after: Optional[str] = None
    note: Optional[str] = None  # e.g. "same cane, comfortable pace"


@dataclass
class FitRecord:
    delivered_on: Optional[str] = None  # YYYY-MM-DD
    checkout: list[CheckItem] = field(default_factory=list)
    tuning: list[TuningRow] = field(default_factory=list)
    measures: list[BeforeAfter] = field(default_factory=list)
    wearing: list[str] = field(default_factory=list)  # wearing time, line by line
    practice: list[str] = field(default_factory=list)  # practice with the orthosis
    training_by: Optional[str] = None  # who set the plan, e.g. "physiotherapist"
    leaflet_ar: Optional[str] = None
    leaflet_en: Optional[str] = None
    leaflet_checked_by: Optional[str] = None  # the Arabic-reading orthotist who checked the Arabic text

    def __post_init__(self) -> None:
        self.delivered_on = check_date(self.delivered_on)
        self.checkout = [c if isinstance(c, CheckItem) else CheckItem(**c) for c in self.checkout]
        self.tuning = [r if isinstance(r, TuningRow) else TuningRow(**r) for r in self.tuning]
        self.measures = [m if isinstance(m, BeforeAfter) else BeforeAfter(**m) for m in self.measures]

    @property
    def empty(self) -> bool:
        return self == FitRecord()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[dict[str, Any]]) -> "FitRecord":
        return cls(**(data or {}))
