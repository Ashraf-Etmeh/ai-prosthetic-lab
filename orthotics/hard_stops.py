"""Hard stops: four DRAFT rules from the design's orthotics map, awaiting the owner's approval.

The map's "Safety built in" (docs/design/03-orthotics/Main.html; SYSTEM_DESIGN.md
§6.2) says: "Hard stops route the case to a doctor", for
- an ulcer with infection or poor blood supply,
- a rigid device on insensate skin without pressure relief,
- a fixed contracture beyond what the design can accommodate,
- FES with an implanted electronic device.

Whether each rule is a draft or the clinic's, in which version, approved by
whom and when, is the owner's to say in data/knowledge/clinic_rules.csv
(knowledge/clinic_rules.py; since 2026-10-24): the pages show each check with
its rule's status. All four are drafts there: SYSTEM_DESIGN.md §11.3 leaves hard
stops to the owner, who answered on 2026-10-24 "not yet, keep as drafts". Every
line quotes the rule instead of saying in the tool's own voice what to do. The code only looks up what
the intake and the plan record, and never infers a value or a device's rigidity.
A draft rule whose recorded facts match it says so; one that needs the
orthotist's judgement says that; one whose facts aren't recorded says it isn't
checked yet. Nothing is blocked: the orthotist and the doctor decide.
"""

from dataclasses import dataclass, field
from typing import Optional

from knowledge.clinic_rules import ClinicRule, rules_for
from orthotics.case import OrthoticCase, SensationStatus
from orthotics.plan import FES_REFERRAL, DesignOption, OrthoticPlan, Part
from shared.case_schema import YesNoUnknown

# How a rule stands for the case, worst first.
STOP = "stop"  # the recorded facts match the rule, which routes the case to a doctor
WARN = "warn"  # the rule applies to part of the design: the orthotist checks it there
JUDGE = "judge"  # only the orthotist can judge it from the recorded value
CLEAR = "clear"  # the recorded facts don't match the rule
NOT_CHECKED = "not_checked"  # what the rule needs isn't recorded (or recorded as unknown)
STATUSES = (STOP, WARN, JUDGE, CLEAR, NOT_CHECKED)

# The rules, in the map's order.
ULCER, INSENSATE, CONTRACTURE, FES_IMPLANT = "ulcer", "insensate", "contracture", "fes_implant"
RULES = (ULCER, INSENSATE, CONTRACTURE, FES_IMPLANT)
# What a check can say it found (i18n "hard_detail.<detail>").
DETAILS = ("ulcer_yes", "ulcer_no", "unknown", "not_recorded", "insensate", "insensate_options", "sensation_intact",
           "contracture", "implant_yes", "implant_fes_chosen", "implant_no", "not_asked")


@dataclass(frozen=True)
class Check:
    rule: str  # one of RULES: its name and the design's wording are i18n "hard.<rule>", "hard_rule.<rule>"
    status: str  # one of STATUSES
    detail: str  # i18n key "hard_detail.<detail>": what the code found, never a clinical sentence
    params: dict = field(default_factory=dict)
    clinic_rule: Optional[ClinicRule] = None  # the rule's row in the owner's file: its status and version


def _ulcer(case: OrthoticCase) -> Check:
    value = case.exam.ulcer_infection_or_poor_blood_supply
    if value is YesNoUnknown.YES:
        return Check(ULCER, STOP, "ulcer_yes")
    if value is YesNoUnknown.NO:
        return Check(ULCER, CLEAR, "ulcer_no")
    return Check(ULCER, NOT_CHECKED, "unknown" if value is YesNoUnknown.UNKNOWN else "not_recorded")


def _insensate(case: OrthoticCase, plan: Optional[OrthoticPlan]) -> Check:
    sensation = case.exam.protective_sensation
    if sensation in (SensationStatus.REDUCED, SensationStatus.ABSENT):
        without = [o.id for o in (plan.options if plan else []) if lacks_lining(case, o)]
        if without:
            return Check(INSENSATE, WARN, "insensate_options", {"ids": ", ".join(without)})
        return Check(INSENSATE, WARN, "insensate", {"value": sensation.value})
    if sensation is SensationStatus.INTACT:
        return Check(INSENSATE, CLEAR, "sensation_intact")
    return Check(INSENSATE, NOT_CHECKED, "unknown" if sensation is SensationStatus.UNKNOWN else "not_recorded")


def _contracture(case: OrthoticCase) -> Check:
    angle = case.exam.dorsiflexion_knee_extended_deg
    if angle is None:
        return Check(CONTRACTURE, NOT_CHECKED, "not_recorded")
    return Check(CONTRACTURE, JUDGE, "contracture", {"n": f"{angle:+g}"})


def _fes(case: OrthoticCase, plan: Optional[OrthoticPlan]) -> Check:
    implanted = case.implanted_electronic_device
    fes_chosen = plan is not None and plan.chosen == FES_REFERRAL
    if implanted is YesNoUnknown.YES:
        return Check(FES_IMPLANT, STOP, "implant_fes_chosen") if fes_chosen else Check(FES_IMPLANT, WARN, "implant_yes")
    if implanted is YesNoUnknown.NO:
        return Check(FES_IMPLANT, CLEAR, "implant_no")
    return Check(FES_IMPLANT, NOT_CHECKED, "unknown" if implanted is YesNoUnknown.UNKNOWN else "not_asked")


def clinic_rules() -> dict[str, ClinicRule]:
    """The four rules' rows in the owner's file (data/knowledge/clinic_rules.csv), by rule id.

    ValueError if the file and RULES differ: a rule the code applies must be in the owner's file, and the
    file names no orthotic hard stop the code doesn't know.
    """
    rows = rules_for("orthotics", "hard_stop")
    if set(rows) != set(RULES):
        raise ValueError(f"data/knowledge/clinic_rules.csv and orthotics/hard_stops.py RULES differ: "
                         f"in the file only {sorted(set(rows) - set(RULES)) or 'none'}, "
                         f"in the code only {sorted(set(RULES) - set(rows)) or 'none'}")
    return rows


def case_checks(case: OrthoticCase, plan: Optional[OrthoticPlan] = None) -> list[Check]:
    """The four rules for this case, in the map's order, each with its row in the owner's file."""
    rows = clinic_rules()
    checks = [_ulcer(case), _insensate(case, plan), _contracture(case), _fes(case, plan)]
    return [Check(c.rule, c.status, c.detail, c.params, rows[c.rule]) for c in checks]


def stops(checks: list[Check]) -> list[Check]:
    return [check for check in checks if check.status == STOP]


def lacks_lining(case: OrthoticCase, option: DesignOption) -> bool:
    """Sensation recorded as reduced or absent, and the option lists no lining (the second rule's check
    on an option card: whether the device is rigid is the orthotist's to say, never the code's)."""
    return (case.exam.protective_sensation in (SensationStatus.REDUCED, SensationStatus.ABSENT)
            and option.device.value != "fes" and not option.has(Part.EVA_LINING))
