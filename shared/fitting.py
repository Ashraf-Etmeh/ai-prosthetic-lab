"""What every domain's design and fitting steps share (SYSTEM_DESIGN.md §5 and §6): a step's status, and the gait
phases an observation is tagged with.

Built for the orthotic modules (orthotics/plan.py steps, orthotics/case.py gait
deviations) and shared since 2026-10-24 with the prosthetic fitting steps
(prosthetics/plan.py). The phases' names are the interface texts "phase.<phase>".
"""

from enum import Enum


class StepStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    NOT_NEEDED = "not_needed"


# The phases of the gait cycle a deviation or an observation is tagged with, in order.
GAIT_PHASES = ("initial_contact", "loading_response", "mid_stance", "terminal_stance", "pre_swing", "swing")
