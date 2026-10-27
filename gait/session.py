"""A case's gait sessions (SYSTEM_DESIGN.md §6.3; docs/design/04-gait-analysis/; plan Part 10, 2026-10-27).

Gait analysis works on a case of either domain, as rehabilitation does (the design's example is a prosthetic case's
session after an alignment change); it is kept with the case (shared/store.py CaseRecord.gait, case file version 6).

PROTOTYPE DECISIONS (Claude, 2026-10-27, at the owner's request while no legal or clinical advice exists; the owner
may change each one):
- This app does not measure movement. The measures come from the capture system (a phone app, wearable sensors,
  pressure insoles or the gait lab's software), entered by hand or imported as a table (CSV_COLUMNS below). Measuring
  from video or sensors is a medical-device function (SYSTEM_DESIGN.md §6.3), so it stays with the system that does
  it; this app only keeps, shows and compares the numbers. No video or sensor file reaches it, so there is nothing to
  blur and nothing that leaves the clinic but the numbers.
- A session from video needs the person's consent to filming, recorded for that session.
- Sessions are records: once saved they are not changed; the specialist's review of an indicator is added to them.
- The measures are a fixed list of common time-distance measures and one joint-angle curve (knee flexion over the
  gait cycle, side view); a measure is per side (left, right) or for both.
"""

import csv
import io
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from shared.dates import check_date


class GaitError(ValueError):
    """A gait session that can't be kept as it is."""


class Source(str, Enum):
    PHONE_VIDEO = "phone_video"  # side and front views; joint angles in 2D
    WEARABLE = "wearable"  # sensors on the shanks and pelvis
    INSOLES = "insoles"  # pressure under each foot through stance
    LAB_3D = "lab_3d"  # the gait lab's motion capture, its exported table
    OTHER = "other"


VIDEO_SOURCES = (Source.PHONE_VIDEO, Source.LAB_3D)  # filmed: consent to filming needed


class Pace(str, Enum):
    COMFORTABLE = "comfortable"
    FAST = "fast"
    SLOW = "slow"


class Marker(str, Enum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    NOT_USED = "not_used"


class ComparisonKind(str, Enum):
    DEVICE_SETTING = "device_setting"  # two sessions that differ in one device setting
    WITH_WITHOUT = "with_without"  # with and without the device
    TWO_DEVICES = "two_devices"  # e.g. foot A against foot C, trial fitting
    BEFORE_AFTER_TRAINING = "before_after_training"


class Mark(str, Enum):
    REVIEWED = "reviewed"
    DISMISSED = "dismissed"  # with a reason


SIDES = ("left", "right")
# Time-distance measures: key -> (unit, per side)
MEASURES = {
    "walking_speed": ("m/s", False),
    "cadence": ("steps/min", False),
    "step_length": ("m", True),
    "stance": ("% of cycle", True),
    "swing": ("% of cycle", True),
    "step_width": ("cm", False),
    "stride_time_cv": ("%", False),  # stride-to-stride variability, as the capture system reports it
}
# Joint-angle curves over the gait cycle (0 to 100 %), per side: key -> unit
CURVES = {"knee_flexion": "°"}
MAX_CURVE_POINTS = 201
CSV_COLUMNS = ("measure", "left", "right", "both")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _enum(cls, value):
    return value if value is None or isinstance(value, cls) else cls(value)


def _number(raw: Any, where: str) -> Optional[float]:
    """A value as a number ("0,92" read as 0.92); None if empty."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    try:
        value = float(str(raw).strip().replace(",", "."))
    except ValueError:
        raise GaitError(f"{where}: not a number: {raw!r}") from None
    if not math.isfinite(value):
        raise GaitError(f"{where}: not a number: {raw!r}")
    return value


def curve_points(raw: Optional[str], where: str) -> list[float]:
    """A curve typed or imported as numbers separated by spaces or semicolons ([] if empty)."""
    parts = [p for p in (raw or "").replace(";", " ").split() if p]
    points = [_number(p, where) for p in parts]
    if points and not 2 <= len(points) <= MAX_CURVE_POINTS:
        raise GaitError(f"{where}: a curve has 2 to {MAX_CURVE_POINTS} points over the gait cycle")
    return points


@dataclass
class Quality:
    """The checks the capture system ran before measuring, as it reports them (or the specialist records them)."""

    frame_rate: Optional[float] = None  # frames per second (video)
    trials: Optional[int] = None
    trials_whole_body: Optional[int] = None  # trials with the whole body in frame
    steps: Optional[int] = None  # steps captured
    hidden_foot_trials: Optional[int] = None  # trials with a foot hidden (left out of that foot's angles)
    hidden_side: Optional[str] = None  # "left" or "right"
    scale_marker: Optional[Marker] = None

    def __post_init__(self) -> None:
        self.scale_marker = _enum(Marker, self.scale_marker)
        if self.hidden_side is not None and self.hidden_side not in SIDES:
            raise GaitError(f"hidden_side must be one of {SIDES}")
        for name in ("trials", "trials_whole_body", "steps", "hidden_foot_trials"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, int) or value < 0):
                raise GaitError(f"{name} must be a whole number from 0")
        if self.trials is not None and self.trials_whole_body is not None and self.trials_whole_body > self.trials:
            raise GaitError("more trials with the whole body in frame than trials")


@dataclass
class Review:
    """The specialist's mark on one indicator of the session: added, never changed."""

    indicator: str  # a threshold id (gait/rules.py)
    mark: Mark
    words: Optional[str]  # the note, or the reason for dismissing (needed)
    at: str

    def __post_init__(self) -> None:
        self.mark = _enum(Mark, self.mark)
        if self.mark is Mark.DISMISSED and not self.words:
            raise GaitError("dismissing an indicator needs a reason")


@dataclass
class Session:
    id: str  # "G1", ...
    on: str  # YYYY-MM-DD
    source: Source
    walkway: Optional[str] = None  # as written, e.g. "10 m corridor"
    pace: Optional[Pace] = None
    device_state: Optional[str] = None  # as written, e.g. "preparatory prosthesis"
    device_version: Optional[str] = None  # "<plan field>:<number>", a versioned record of the case's plan
    footwear: Optional[str] = None
    aid: Optional[str] = None  # walking aid, as written ("none")
    filming_consent: Optional[bool] = None  # for a filmed session: the person agreed to filming
    quality: Quality = field(default_factory=Quality)
    values: dict[str, dict[str, float]] = field(default_factory=dict)  # measure -> {"left"|"right"|"both": value}
    curves: dict[str, dict[str, list[float]]] = field(default_factory=dict)  # curve -> {side: points}
    notes: Optional[str] = None
    saved_at: str = ""
    reviews: list[Review] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.source = _enum(Source, self.source)
        self.pace = _enum(Pace, self.pace)
        check_date(self.on)
        if not isinstance(self.quality, Quality):
            self.quality = Quality(**(self.quality or {}))
        self.reviews = [r if isinstance(r, Review) else Review(**r) for r in self.reviews]
        if self.source in VIDEO_SOURCES and self.filming_consent is not True:
            raise GaitError("a filmed session needs the person's consent to filming")
        for measure, by_side in self.values.items():
            if measure not in MEASURES:
                raise GaitError(f"unknown measure {measure!r}")
            allowed = set(SIDES) if MEASURES[measure][1] else {"both"}
            if set(by_side) - allowed:
                raise GaitError(f"{measure}: values are for {sorted(allowed)}")
        for curve, by_side in self.curves.items():
            if curve not in CURVES or set(by_side) - set(SIDES):
                raise GaitError(f"unknown curve {curve!r}")

    def value(self, measure: str, side: str = "both") -> Optional[float]:
        return self.values.get(measure, {}).get(side)

    def review_of(self, indicator: str) -> Optional[Review]:
        return next((r for r in reversed(self.reviews) if r.indicator == indicator), None)

    @property
    def filmed(self) -> bool:
        return self.source in VIDEO_SOURCES


@dataclass
class Comparison:
    """Two sessions compared and sent to the case (module 4): which, what kind, the specialist's note."""

    first: str
    second: str
    kind: ComparisonKind
    saved_at: str
    note: Optional[str] = None

    def __post_init__(self) -> None:
        self.kind = _enum(ComparisonKind, self.kind)


@dataclass
class GaitRecord:
    sessions: list[Session] = field(default_factory=list)
    comparisons: list[Comparison] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.sessions = [s if isinstance(s, Session) else Session(**s) for s in self.sessions]
        self.comparisons = [c if isinstance(c, Comparison) else Comparison(**c) for c in self.comparisons]
        ids = [s.id for s in self.sessions]
        if len(set(ids)) != len(ids):
            raise GaitError("each session has its own id")
        for c in self.comparisons:
            if not {c.first, c.second} <= set(ids) or c.first == c.second:
                raise GaitError("a comparison names two different sessions of the case")

    def session(self, session_id: Optional[str]) -> Optional[Session]:
        return next((s for s in self.sessions if s.id == session_id), None)

    def next_id(self) -> str:
        numbers = [int(s.id[1:]) for s in self.sessions if s.id[1:].isdigit()]
        return f"G{max(numbers, default=0) + 1}"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for session in data["sessions"]:
            for name in ("source", "pace"):
                if isinstance(session[name], Enum):
                    session[name] = session[name].value
            if isinstance(session["quality"]["scale_marker"], Enum):
                session["quality"]["scale_marker"] = session["quality"]["scale_marker"].value
            for review in session["reviews"]:
                review["mark"] = Mark(review["mark"]).value
        for comparison in data["comparisons"]:
            comparison["kind"] = ComparisonKind(comparison["kind"]).value
        return data

    @classmethod
    def from_dict(cls, data: Optional[dict[str, Any]]) -> "GaitRecord":
        return cls(**(data or {}))


# ---- Importing the capture system's table ---------------------------------------------------------------------


def read_table(text: str) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, list[float]]]]:
    """(values, curves) from a CSV with the columns measure, left, right, both: one row per measure (a per-side
    measure in left and right, the others in both), a curve's points in left and right, separated by spaces or
    semicolons. GaitError if a row can't be used."""
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    if tuple(name.strip().lower() for name in (reader.fieldnames or ())) != CSV_COLUMNS:
        raise GaitError(f"the table's columns must be {', '.join(CSV_COLUMNS)}")
    values: dict[str, dict[str, float]] = {}
    curves: dict[str, dict[str, list[float]]] = {}
    for row in reader:
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        measure = row["measure"]
        if not measure:
            continue
        if measure in CURVES:
            by_side = {side: curve_points(row[side], f"{measure}, {side}") for side in SIDES if row[side]}
            if by_side:
                curves[measure] = by_side
            continue
        if measure not in MEASURES:
            raise GaitError(f"unknown measure {measure!r}")
        sided = MEASURES[measure][1]
        sides = SIDES if sided else ("both",)
        other = ("both",) if sided else SIDES
        if any(row[column] for column in other):
            raise GaitError(f"{measure}: its values go in {' and '.join(sides)}")
        by_side = {side: _number(row[side], f"{measure}, {side}") for side in sides}
        by_side = {side: value for side, value in by_side.items() if value is not None}
        if by_side:
            values[measure] = by_side
    return values, curves


def table_template() -> str:
    """The table to fill in: every measure and curve, empty."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(CSV_COLUMNS)
    for measure in [*MEASURES, *CURVES]:
        writer.writerow([measure, "", "", ""])
    return out.getvalue()
