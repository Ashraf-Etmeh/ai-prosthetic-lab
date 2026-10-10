"""The owner's evidence rule table, applied to the knowledge items.

  python -m knowledge.evidence_rules     applies data/knowledge/evidence_rules.csv and
                                         writes items.json and items_to_curate.csv

data/knowledge/evidence_rules.csv is the owner's: one row per rule, with the
columns rule_id, matches (the owner's words), evidence_layer, evidence_tag,
confidence and basis. Code never writes or changes it. CONDITIONS below
turns each rule's "matches" into a condition on the item's catalog document,
grade as printed and, where those can't tell items apart, knowledge id; the
owner approved each one (2026-10-10, FUTURE_WORK.md).

For each item:
- exactly one rule matches: the item gets that rule's evidence_layer,
  evidence_tag and confidence, validation_status "rule-assigned" and
  assigned_by the rule id. "unassigned" in the table is the owner's choice
  and is copied like any other value.
- a "per item" rule or no rule matches: its evidence values stay
  "unassigned" (the item goes to items_to_curate.csv).
- more than one rule matches: nothing is applied or written; the error
  names each such item and its rules.
Rules never touch population or limitations, and never overwrite evidence
values set by hand or a reviewed item: such a match is an error too.
"""

import csv
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional

from knowledge.models import (
    CONFIDENCE_LEVELS,
    EVIDENCE_LAYERS,
    EVIDENCE_TAGS,
    REVIEWED,
    RULE_ID,
    UNASSIGNED,
    KnowledgeItem,
)
from shared.config import EVIDENCE_RULES_PATH

COLUMNS = ("rule_id", "matches", "evidence_layer", "evidence_tag", "confidence", "basis")
# In the evidence_layer column: the rule sets nothing; its items are classified one by one.
PER_ITEM = "per item"


@dataclass(frozen=True)
class EvidenceRule:
    """One row of the owner's table, as written."""

    rule_id: str
    matches: str
    evidence_layer: str
    evidence_tag: str
    confidence: str
    basis: str

    def __post_init__(self) -> None:
        if not RULE_ID.fullmatch(self.rule_id):
            raise ValueError(f"rule_id must be like 'R1', got {self.rule_id!r}")
        if self.per_item:
            for name in ("evidence_tag", "confidence"):
                if getattr(self, name) not in (PER_ITEM, ""):
                    raise ValueError(f"{self.rule_id}: a '{PER_ITEM}' rule sets nothing, but its {name} "
                                     f"is {getattr(self, name)!r}; leave it empty or '{PER_ITEM}'")
            return
        for name, allowed in (("evidence_layer", EVIDENCE_LAYERS), ("evidence_tag", EVIDENCE_TAGS),
                              ("confidence", CONFIDENCE_LEVELS)):
            if getattr(self, name) not in allowed:
                raise ValueError(f"{self.rule_id}: {name} must be one of {list(allowed)}"
                                 f"{f' (or {PER_ITEM!r} in evidence_layer)' if name == 'evidence_layer' else ''}, "
                                 f"got {getattr(self, name)!r}")

    @property
    def per_item(self) -> bool:
        return self.evidence_layer == PER_ITEM


@dataclass(frozen=True)
class Condition:
    """Which items a rule matches: all the parts given must hold."""

    source_ids: frozenset[str]  # catalog ids of the documents
    grades: Optional[frozenset[str]] = None  # grade_as_printed, exactly; None: any
    knowledge_ids: Optional[frozenset[str]] = None  # only these items; None: any
    except_knowledge_ids: frozenset[str] = frozenset()

    def matches(self, item: KnowledgeItem) -> bool:
        return (item.source_id in self.source_ids
                and (self.grades is None or item.grade_as_printed in self.grades)
                and (self.knowledge_ids is None or item.knowledge_id in self.knowledge_ids)
                and item.knowledge_id not in self.except_knowledge_ids)


VA_DOD = frozenset({"lower_limb_amputation_va_dod_cpg_2024", "upper_limb_amputation_va_dod_cpg_2022"})
CMS = frozenset({"lower_limb_prosthesis_cms_consensus_2017"})
K_LEVEL_DESCRIPTIONS = frozenset(f"cms_k{n}_description" for n in range(5))
# "parts 1 and 2, any language": the catalog dates the Arabic editions 2019.
WHO_STANDARDS = frozenset({"who_po_standards_part1_2017", "who_po_implementation_manual_part2_2017",
                           "who_po_standards_part1_arabic_2019", "who_po_implementation_manual_part2_arabic_2019"})
ICRC_MANUAL = frozenset({"prosthetic_gait_analysis_icrc_manual_2014"})

CONDITIONS: dict[str, Condition] = {
    "R1": Condition(VA_DOD, grades=frozenset({"Strong for", "Strong against"})),
    "R2": Condition(VA_DOD, grades=frozenset({"Weak for", "Weak against"})),
    "R3": Condition(VA_DOD, grades=frozenset({"Neither for nor against"})),
    "R4": Condition(VA_DOD, grades=frozenset({""})),  # "no printed grade"
    # The CMS statements all have no grade, so the knowledge ids tell them apart.
    "R5": Condition(CMS, knowledge_ids=K_LEVEL_DESCRIPTIONS),
    "R6": Condition(CMS, except_knowledge_ids=K_LEVEL_DESCRIPTIONS),
    "R7": Condition(WHO_STANDARDS),
    "R8": Condition(ICRC_MANUAL),
}


def load_rules(path: Path = EVIDENCE_RULES_PATH, conditions: dict[str, Condition] = CONDITIONS) -> list[EvidenceRule]:
    """The owner's rules, each checked. ValueError if any is not valid or has no condition here."""
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if set(reader.fieldnames or ()) != set(COLUMNS):
            raise ValueError(f"{path}: the columns must be exactly {', '.join(COLUMNS)}; "
                             f"got {', '.join(reader.fieldnames or ())}")
        rows = list(reader)
    rules = []
    for number, row in enumerate(rows, start=2):  # row 1 is the header
        if None in row:  # csv puts cells beyond the header under None
            raise ValueError(f"{path}, row {number}: more cells than columns")
        if not any((value or "").strip() for value in row.values()):
            continue  # an empty line, e.g. left by a spreadsheet
        try:
            rules.append(EvidenceRule(**{name: row[name] or "" for name in COLUMNS}))
        except ValueError as error:
            raise ValueError(f"{path}, row {number}: {error}") from None
    ids = [rule.rule_id for rule in rules]
    repeated = sorted({i for i in ids if ids.count(i) > 1})
    if repeated:
        raise ValueError(f"{path}: rule ids used more than once: {', '.join(repeated)}")
    if set(ids) != set(conditions):
        raise ValueError(f"{path}: the table and the conditions in knowledge/evidence_rules.py differ; "
                         f"in the table only: {sorted(set(ids) - set(conditions)) or 'none'}, "
                         f"in the conditions only: {sorted(set(conditions) - set(ids)) or 'none'}")
    return rules


def _keeps_its_values(item: KnowledgeItem) -> bool:
    """Evidence values set by hand, or reviewed: no rule may replace them."""
    return item.assigned_by == "manual" or item.validation_status in REVIEWED


def apply_rules(items: list[KnowledgeItem], rules: list[EvidenceRule],
                conditions: dict[str, Condition] = CONDITIONS) -> list[KnowledgeItem]:
    """The items with the rules applied. Changes only the evidence values, validation_status and assigned_by."""
    without_condition = [rule.rule_id for rule in rules if rule.rule_id not in conditions]
    if without_condition:
        raise ValueError(f"no condition for {', '.join(without_condition)} in knowledge/evidence_rules.py")
    problems, result = [], []
    for item in items:
        matching = [rule for rule in rules if conditions[rule.rule_id].matches(item)]
        if len(matching) > 1:
            problems.append(f"{item.knowledge_id} matches {', '.join(rule.rule_id for rule in matching)}")
            continue
        rule = matching[0] if matching else None
        if _keeps_its_values(item):
            if rule and not rule.per_item:
                problems.append(f"{item.knowledge_id} matches {rule.rule_id}, but its evidence values were "
                                f"set by hand or reviewed ({', '.join(item.kept_by_team())}); rules don't replace them")
            result.append(item)
        elif rule and not rule.per_item:
            result.append(replace(item, evidence_layer=rule.evidence_layer, evidence_tag=rule.evidence_tag,
                                  confidence=rule.confidence, validation_status="rule-assigned",
                                  assigned_by=rule.rule_id))
        else:  # no rule, or "per item": unassigned (also undoes a rule that no longer matches)
            result.append(replace(item, evidence_layer=UNASSIGNED, evidence_tag=UNASSIGNED,
                                  confidence=UNASSIGNED, validation_status="unreviewed", assigned_by="none"))
    if problems:
        raise ValueError("Rules not applied, nothing written: " + "; ".join(problems))
    return result


def main(argv=None) -> None:
    from knowledge import items  # here: knowledge.items imports this module

    items.main(argv, prog="python -m knowledge.evidence_rules")


if __name__ == "__main__":
    main()
