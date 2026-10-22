"""The topics of a case's RAG: what is searched, and what the model is asked about.

Three parts, one model call each (reasoning/rag.py):
- "gaps": one topic per missing intake field (shared/field_guide.py), with
  the field guide's own search text.
- "components": the case's functional level (lower limb only: K-levels
  describe lower-limb prostheses) and one topic per prosthetic component.
- "fitting": readiness, preparatory or definitive prosthesis, fitting, and
  alignment.

The component and fitting sections are those of reasoning/component_guide.py
COMPONENTS and reasoning/fitting_guide.py SECTIONS, with the levels they
apply to. The pylon has no levels there (it was listed only when a statement
applied); here it is searched for every lower-limb case and listed only when
the model reports something.

The search text names the case's amputation level and limb, "bilateral" for
a bilateral case (left and right are not named), and the recorded K-level, so
the passages found are the ones closest to this case. It decides nothing: the
model reports what the passages say, and the specialist decides.
"""

from dataclasses import dataclass

from reasoning.component_guide import COMPONENTS, LOWER
from reasoning.component_support import recorded_k_level
from reasoning.fitting_guide import SECTIONS
from shared.case_schema import Case, Side
from shared.field_guide import build_query, missing_fields

GAPS, COMPONENTS_PART, FITTING = "gaps", "components", "fitting"
PARTS = (GAPS, COMPONENTS_PART, FITTING)
FUNCTIONAL_LEVEL = "functional_level"


@dataclass(frozen=True)
class Topic:
    key: str  # a gap's field path, a component or fitting section key, or "functional_level"
    part: str  # GAPS, COMPONENTS_PART or FITTING
    label: str  # English, for the model
    query: str  # the search text


# Component and fitting topics: label for the model, and what to search for.
_SECTION_TOPICS = {
    "knee": ("Knee unit", "prosthetic knee unit: microprocessor or non-microprocessor knee"),
    "foot_ankle": ("Foot and ankle", "prosthetic foot and ankle: energy storing, microprocessor or powered ankle"),
    "pylon": ("Pylon", "prosthetic pylon: shock absorbing or torsion pylon"),
    "socket": ("Socket", "prosthetic socket design and socket fit"),
    "interface": ("Interface (liner or socket insert)", "socket interface: liner, socks, gel or soft insert"),
    "suspension": ("Suspension", "prosthetic suspension: suction, pin lock, sleeve, vacuum or belt"),
    "prosthesis_type": ("Type of prosthesis",
                        "type of upper limb prosthesis: body-powered, myoelectric, passive or activity-specific"),
    "control_and_fit": ("Control strategy, socket, suspension and components",
                        "upper limb prosthesis control strategy, socket, harness and suspension"),
    "readiness": ("Readiness for fitting",
                  "readiness for prosthetic fitting: wound healing, oedema and volume, skin, pain, "
                  "contracture and general condition before fitting"),
    "prosthesis_stage": ("Preparatory or definitive prosthesis",
                         "preparatory (temporary) prosthesis or definitive prosthesis, and when"),
    "fitting": ("Fitting, check-out and follow-up",
                "prosthesis fitting process: check socket, fitting, check-out, delivery and follow-up"),
    "alignment": ("Alignment",
                  "prosthetic alignment: bench, static and dynamic alignment, and gait deviations "
                  "caused by alignment errors"),
}


def case_words(case: Case) -> str:
    """E.g. "transfemoral amputation (lower limb), bilateral, functional level K2"."""
    limb = "lower limb" if case.is_lower_limb else "upper limb"
    words = f"{case.amputation_level.value.replace('_', ' ')} amputation ({limb})"
    if case.side is Side.BILATERAL:
        words += ", bilateral"
    k_level = recorded_k_level(case)
    if k_level:
        words += f", functional level {k_level}"
    return words


def _functional_topic(case: Case) -> Topic:
    k_level = recorded_k_level(case)
    if k_level:
        query = (f"Medicare functional classification level {k_level}: how {k_level} is described, "
                 "ability or potential to ambulate")
    else:
        query = "Medicare functional classification levels K0 K1 K2 K3 K4: descriptions of ambulation potential"
    return Topic(FUNCTIONAL_LEVEL, COMPONENTS_PART, "Functional level (K-level)", query)


def _section_topic(key: str, part: str, case: Case) -> Topic:
    label, query = _SECTION_TOPICS[key]
    return Topic(key, part, label, f"{query} ({case_words(case)})")


def _component_searched(key: str, levels, case: Case) -> bool:
    if key == "pylon":
        return case.amputation_level in LOWER
    return case.amputation_level in levels


def topics_for_case(case: Case) -> list[Topic]:
    """Every topic of the case, part by part, in the order the review page shows them."""
    topics = [Topic(missing.info.path, GAPS, missing.info.label, build_query(case, missing.info))
              for missing in missing_fields(case)]
    if case.is_lower_limb:
        topics.append(_functional_topic(case))
    topics += [_section_topic(info.key, COMPONENTS_PART, case)
               for info in COMPONENTS if _component_searched(info.key, info.levels, case)]
    topics += [_section_topic(info.key, FITTING, case)
               for info in SECTIONS if case.amputation_level in info.levels]
    return topics
