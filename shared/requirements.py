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
from typing import Optional


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
