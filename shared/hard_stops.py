"""Hard-stop checks (SYSTEM_DESIGN.md §5), the same for every domain: how a clinic rule stands for a case.

The rules are the clinic's, each with its status (draft or approved), version, owner
and approval date in data/knowledge/clinic_rules.csv (knowledge/clinic_rules.py).
A domain applies its rules to what the case records (prosthetics/hard_stops.py,
orthotics/hard_stops.py) and says, for each, one of the statuses below with what it
found; the page shows each check with its rule's status (shared/templates/ui_macros.html
hard_stop_list). A triggered check routes the case to a person; it never decides
and nothing is blocked.
"""

from dataclasses import dataclass, field
from typing import Optional

from knowledge.clinic_rules import ClinicRule, rules_for

# How a rule stands for the case, worst first.
STOP = "stop"  # the recorded facts match the rule, which routes the case to a person
WARN = "warn"  # the rule applies to part of the case or the design: the specialist checks it there
JUDGE = "judge"  # only the specialist can judge it from the recorded value
CLEAR = "clear"  # the recorded facts don't match the rule
NOT_CHECKED = "not_checked"  # what the rule needs isn't recorded (or recorded as unknown)
STATUSES = (STOP, WARN, JUDGE, CLEAR, NOT_CHECKED)


@dataclass(frozen=True)
class Check:
    rule: str  # the rule's id: its name and wording are i18n "hard.<rule>", "hard_rule.<rule>"
    status: str  # one of STATUSES
    detail: str  # i18n key "hard_detail.<detail>": what the code found, never a clinical sentence
    params: dict = field(default_factory=dict)
    clinic_rule: Optional[ClinicRule] = None  # the rule's row in the owner's file: its status and version


def clinic_rules(domain: str, rules: tuple[str, ...]) -> dict[str, ClinicRule]:
    """The domain's hard stops in the owner's file, by rule id.

    ValueError if the file and the code differ: a rule the code applies must be in the owner's file, and the
    file names no hard stop of this domain that the code doesn't know.
    """
    rows = rules_for(domain, "hard_stop")
    if set(rows) != set(rules):
        raise ValueError(f"data/knowledge/clinic_rules.csv and {domain}/hard_stops.py RULES differ: "
                         f"in the file only {sorted(set(rows) - set(rules)) or 'none'}, "
                         f"in the code only {sorted(set(rules) - set(rows)) or 'none'}")
    return rows


def with_rules(domain: str, rules: tuple[str, ...], checks: list[Check]) -> list[Check]:
    """The checks, each with its rule's row in the owner's file."""
    rows = clinic_rules(domain, rules)
    return [Check(c.rule, c.status, c.detail, c.params, rows[c.rule]) for c in checks]


def stops(checks: list[Check]) -> list[Check]:
    return [check for check in checks if check.status == STOP]
