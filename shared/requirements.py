"""Requirements before devices (SYSTEM_DESIGN.md §5), shared by every domain's modules.

Each requirement is a function the device must perform ("clear the toes in
swing"), never a device, in the specialist's words. It keeps where it came from
in the case (a gait problem, an exam value or a goal: the domain's finding keys,
e.g. orthotics/plan.py case_findings()) and the specialist's priority. Conflicts
between requirements are written down, not hidden, and each option is marked by
the specialist against each requirement (yes, partly or no). The tool writes none
of these.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class PlanError(ValueError):
    """A specialist's plan that can't be kept as it is (raised before anything is saved)."""


class Priority(str, Enum):
    MUST = "must"
    SHOULD = "should"
    NICE = "nice"


class Mark(str, Enum):
    """The specialist's mark: does this option address that requirement?"""

    YES = "yes"
    PARTLY = "partly"
    NO = "no"


@dataclass
class Requirement:
    id: str  # "R1", "R2", ...: kept when the text changes
    text: str  # the specialist's words
    # What it comes from: the domain's finding keys (a deviation, or a value's path, recorded or not).
    findings: list[str] = field(default_factory=list)
    priority: Optional[Priority] = None

    def __post_init__(self) -> None:
        self.priority = None if self.priority is None else Priority(self.priority)


@dataclass
class Conflict:
    """Two requirements that pull against each other, and the specialist's note on it."""

    first: str  # requirement ids
    second: str
    note: str


def next_requirement_id(requirements: list[Requirement]) -> str:
    """The next free "R<n>" after the highest number used."""
    numbers = [int(r.id[1:]) for r in requirements if r.id[1:].isdigit()]
    return f"R{max(numbers, default=0) + 1}"


def check_requirements(requirements: list[Requirement], known_findings: set[str]) -> None:
    """PlanError unless the ids are distinct, each has its text, and each names only findings of the case."""
    ids = [r.id for r in requirements]
    if len(ids) != len(set(ids)):
        raise PlanError("repeated requirement id")
    for r in requirements:
        if not r.text.strip():
            raise PlanError("a requirement without text")
        unknown = set(r.findings) - known_findings
        if unknown:
            raise PlanError(f"{r.id}: not a finding of this case: {sorted(unknown)}")


def check_conflicts(conflicts: list[Conflict], requirements: list[Requirement]) -> None:
    """PlanError unless each conflict is between two different requirements and has its note."""
    known = {r.id for r in requirements}
    for c in conflicts:
        if {c.first, c.second} - known or c.first == c.second:
            raise PlanError("a conflict is between two different requirements of this plan")
        if not c.note.strip():
            raise PlanError("a conflict without a note")


# ---- What a requirement comes from in the case ------------------------------------


@dataclass(frozen=True)
class Finding:
    """Something the case recorded (or doesn't yet) that a requirement can come from."""

    key: str  # what a requirement names: a value's path, or the domain's own key (e.g. "deviation.toe_drag")
    group: str  # how the requirements page groups it (the domain's groups; "missing": not recorded yet)
    path: Optional[str]  # the value's path, whose label names it (None: the domain names it, e.g. a deviation)
    value: Any  # as recorded: an enum, a number or text; None: not recorded yet


def value_at(obj, path: str):
    """The value at a dotted path ("exam.foot_posture") of a case or a plan."""
    value = obj
    for name in path.split("."):
        value = getattr(value, name)
    return value


def recorded(value) -> bool:
    """Whether a value is recorded: not None, and not "unknown" (an empty list is recorded: asked, none)."""
    return value is not None and getattr(value, "value", None) != "unknown"
