"""Component selection support: what the guidelines say about this case's components.

The brief's use case 02 ("support component selection based on the
functional data") and pathway step 04 ("assistive recommendations").

For a case, this returns:
1. The functional level the choice depends on: for a lower-limb case the
   CMS description of the recorded K-level, with the source's cautions
   about what a K-level is, and the patient's recorded activity and goals.
2. Per component (knee, foot and ankle, socket, ...): the statements in
   reasoning/component_guide.py that apply to the case, quoted word for
   word with their source, page and grade.
3. Notes on statements left out because the case lacks a K-level, or
   because K0 is recorded.

IMPORTANT: this never chooses, ranks or recommends a component. It only
shows what the cited sources say, so the specialist can check each
statement against its page; the specialist decides.
"""

from functools import lru_cache
from typing import Optional

from knowledge.catalog import load_catalog
from reasoning.component_guide import COMPONENTS, K_LEVEL_CAUTIONS, K_LEVEL_DESCRIPTIONS, RULES, Rule
from reasoning.models import (
    CitedStatement,
    ComponentSection,
    ComponentSupport,
    FunctionalLevel,
    GuidelineStatement,
)
from shared.case_schema import ActivityLevel, Case, Side

NOTE_K_NOT_RECORDED = "components.k_not_recorded"
NOTE_K0 = "components.k0"


@lru_cache(maxsize=1)
def _documents() -> dict[str, tuple[str, Optional[int], str, str]]:
    """Catalog id -> (title, year, language, source type)."""
    return {doc.id: (doc.title, doc.year, doc.language, doc.source_type) for doc in load_catalog()}


def cite(statement: GuidelineStatement) -> CitedStatement:
    return CitedStatement(statement, *_documents()[statement.doc_id])


def recorded_k_level(case: Case) -> Optional[str]:
    """"K0".."K4", or None if not recorded, recorded as unknown, or upper limb."""
    level = case.activity.k_level
    if not case.is_lower_limb or level is None or level is ActivityLevel.UNKNOWN:
        return None
    return level.value


def applies(rule: Rule, case: Case) -> bool:
    k_level = recorded_k_level(case)
    if case.amputation_level not in rule.levels:
        return False
    if rule.unilateral_only and case.side is Side.BILATERAL:
        return False
    if rule.bilateral_only and case.side is not Side.BILATERAL:
        return False
    if rule.k_levels is not None and k_level not in rule.k_levels:
        return False
    if rule.ambulators_only and k_level == "K0":
        return False
    return True


def functional_level(case: Case) -> FunctionalLevel:
    k_level = recorded_k_level(case)
    functional = FunctionalLevel(
        lower_limb=case.is_lower_limb,
        k_level=k_level,
        activity=case.activity.description,
        goals=case.activity.functional_goals,
    )
    if case.is_lower_limb:
        functional.description = cite(K_LEVEL_DESCRIPTIONS[k_level]) if k_level else None
        functional.all_levels = [cite(statement) for statement in K_LEVEL_DESCRIPTIONS.values()]
        functional.cautions = [cite(statement) for statement in K_LEVEL_CAUTIONS]
    return functional


def component_support(case: Case) -> ComponentSupport:
    matching = [rule.statement for rule in RULES if applies(rule, case)]
    sections = []
    for info in COMPONENTS:
        statements = [cite(s) for s in matching if s.component == info.key]
        if statements or case.amputation_level in info.levels:
            sections.append(ComponentSection(info.key, statements))

    notes = []
    if case.is_lower_limb:
        k_level = recorded_k_level(case)
        if k_level is None:
            notes.append(NOTE_K_NOT_RECORDED)
        elif k_level == "K0":
            notes.append(NOTE_K0)
    return ComponentSupport(functional_level(case), sections, notes)
