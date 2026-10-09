"""Design and fitting support: what the sources say about fitting this case.

The brief's prosthetics domain: "evaluate the amputation, choose the
components, design and fit". For a case, this returns:
1. Per section (readiness, preparatory or definitive prosthesis, fitting,
   alignment): the statements in reasoning/fitting_guide.py that apply to
   the case, quoted word for word with their source and page.
2. What the case recorded for the intake fields the readiness statements
   speak about (wounds, volume, skin, pain, ...), shown as entered.

IMPORTANT: this never says whether a patient is ready, which prosthesis to
fit, or how to align it. It shows what the cited sources say next to what
was recorded; the specialist decides.
"""

from reasoning.component_support import applies, cite
from reasoning.fitting_guide import READINESS_FIELDS, RULES, SECTIONS
from reasoning.models import ComponentSection, FittingSupport
from shared.case_schema import Case


def recorded_value(case: Case, path: str) -> object:
    """The value of a dotted field path, e.g. "residual_limb.pain", as recorded."""
    value = case
    for name in path.split("."):
        value = getattr(value, name)
    return value


def fitting_support(case: Case) -> FittingSupport:
    matching = [rule.statement for rule in RULES if applies(rule, case)]
    sections = [
        ComponentSection(info.key, [cite(s) for s in matching if s.component == info.key])
        for info in SECTIONS
        if case.amputation_level in info.levels
    ]
    recorded = [(path, recorded_value(case, path)) for path in READINESS_FIELDS]
    return FittingSupport(sections, recorded)
