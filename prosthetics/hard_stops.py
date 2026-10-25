"""Hard stops: three DRAFT rules from the design's prosthetics module 1, awaiting the owner's approval.

The design's assessment page (docs/design/02-prosthetics/Main.html; SYSTEM_DESIGN.md
§6.1, "Hard-stop checks, for example an open wound or infection, a still-changing
volume, or a neuropathic other foot") lists:
- an open wound or infection,
- a changing volume: "a definitive socket waits for stable volume: the prosthetist
  decides when",
- a neuropathic other foot: "referral to the diabetic foot team, if not under its care".

The owner asked on 2026-10-24 to add them as drafts. Whether each is a draft or the
clinic's rule, in which version, approved by whom and when, is the owner's to say in
data/knowledge/clinic_rules.csv (knowledge/clinic_rules.py); the pages show each
check with its rule's status (shared/hard_stops.py). The code only looks up what the
intake and module 1 record (the wound and volume at intake; infection, the other
foot and the diabetic foot team on module 1, prosthetics/plan.py Assessment) and
never infers a value. A rule whose recorded facts match it says so; one that needs
the prosthetist's judgement says that; one whose facts aren't recorded says it isn't
checked yet. Nothing is blocked: the prosthetist and the person the rule routes the
case to decide.
"""

from typing import Optional

from knowledge.clinic_rules import ClinicRule
from prosthetics.case import Case, VolumeStability, WoundStatus
from prosthetics.plan import ProstheticPlan
from shared import hard_stops as shared
from shared.case_schema import YesNoUnknown
from shared.hard_stops import CLEAR, JUDGE, NOT_CHECKED, STOP, WARN, Check

# The rules, in the design's order.
OPEN_WOUND, VOLUME_CHANGING, NEUROPATHIC_FOOT = "open_wound", "volume_changing", "neuropathic_foot"
RULES = (OPEN_WOUND, VOLUME_CHANGING, NEUROPATHIC_FOOT)
# What a check can say it found (i18n "hard_detail.<detail>").
DETAILS = ("wound_open", "infection_yes", "wound_healing", "wound_healed_no_infection", "infection_not_recorded",
           "unknown", "not_recorded", "volume_fluctuating", "volume_stable", "neuropathy_no", "team_care",
           "team_refer", "team_unknown")


def _not_checked(value) -> str:
    """Why a rule isn't checked: its value is recorded as unknown, or not recorded."""
    return "unknown" if value is not None else "not_recorded"


def _open_wound(case: Case, plan: Optional[ProstheticPlan]) -> Check:
    wound = case.residual_limb.wound_status
    infection = plan.assessment.infection if plan else None
    if wound is WoundStatus.OPEN:
        return Check(OPEN_WOUND, STOP, "wound_open")
    if infection is YesNoUnknown.YES:
        return Check(OPEN_WOUND, STOP, "infection_yes")
    if wound is WoundStatus.HEALING:
        return Check(OPEN_WOUND, JUDGE, "wound_healing")
    if wound is WoundStatus.HEALED:
        if infection is YesNoUnknown.NO:
            return Check(OPEN_WOUND, CLEAR, "wound_healed_no_infection")
        return Check(OPEN_WOUND, NOT_CHECKED, "infection_not_recorded")
    return Check(OPEN_WOUND, NOT_CHECKED, _not_checked(wound))


def _volume(case: Case) -> Check:
    volume = case.residual_limb.volume_stability
    if volume is VolumeStability.FLUCTUATING:
        return Check(VOLUME_CHANGING, WARN, "volume_fluctuating")
    if volume is VolumeStability.STABLE:
        return Check(VOLUME_CHANGING, CLEAR, "volume_stable")
    return Check(VOLUME_CHANGING, NOT_CHECKED, _not_checked(volume))


def _neuropathic_foot(plan: Optional[ProstheticPlan]) -> Check:
    neuropathy = plan.assessment.other_foot_neuropathy if plan else None
    team = plan.assessment.diabetic_foot_team if plan else None
    if neuropathy is YesNoUnknown.YES:
        if team is YesNoUnknown.YES:
            return Check(NEUROPATHIC_FOOT, CLEAR, "team_care")
        if team is YesNoUnknown.NO:
            return Check(NEUROPATHIC_FOOT, STOP, "team_refer")
        return Check(NEUROPATHIC_FOOT, WARN, "team_unknown")
    if neuropathy is YesNoUnknown.NO:
        return Check(NEUROPATHIC_FOOT, CLEAR, "neuropathy_no")
    return Check(NEUROPATHIC_FOOT, NOT_CHECKED, "unknown" if neuropathy is YesNoUnknown.UNKNOWN else "not_recorded")


def clinic_rules() -> dict[str, ClinicRule]:
    """The three rules' rows in the owner's file (data/knowledge/clinic_rules.csv), by rule id (ValueError if the
    file and RULES differ)."""
    return shared.clinic_rules("prosthetics", RULES)


def case_checks(case: Case, plan: Optional[ProstheticPlan] = None) -> list[Check]:
    """The rules for this case, in the design's order, each with its row in the owner's file. The other foot's
    rule is for a lower-limb case only."""
    checks = [_open_wound(case, plan), _volume(case)]
    if case.is_lower_limb:
        checks.append(_neuropathic_foot(plan))
    return shared.with_rules("prosthetics", RULES, checks)
