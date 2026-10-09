"""What the guidelines in the library say about prosthetic components.

Hand-written, like shared/field_guide.py: each rule holds one statement
copied word for word from a catalogued document, with its page and the
source's own grade, and says which cases it applies to. Who a rule applies
to comes from the source's own wording:
- amputation levels: a knee statement only for levels with a prosthetic knee,
  upper-limb recommendation 7 only "through or proximal to the wrist",
- "unilateral": not shown for bilateral cases,
- "at the K2 level": shown only when K2 is recorded,
- "prosthetic ambulators" / "community ambulators": not shown when K0 is
  recorded, which the CMS document describes as no ability or potential to
  ambulate or transfer safely.

Nothing here ranks options or adds advice. Where the sources differ (e.g.
microprocessor knees at K2: VA/DoD 2024 "Weak for", CMS 2017 "may
benefit"), both are shown and the specialist weighs them.

tests/test_component_guide.py checks that every quote is on its page in
data/extracted/<doc_id>.txt. Each quote is one or more whole sentences.

To add a statement: copy the sentences from the extracted text, note the
page from its "--- page N ---" marker, add a Rule, and run the tests.
"""

from dataclasses import dataclass
from typing import Optional

from reasoning.models import GuidelineStatement, Quote
from shared.case_schema import AmputationLevel as Level

LOWER = frozenset(level for level in Level if level.is_lower_limb)
UPPER = frozenset(level for level in Level if not level.is_lower_limb)
# "major unilateral upper limb amputation (i.e., through or proximal to the wrist)"
MAJOR_UPPER = UPPER - {Level.PARTIAL_HAND}
WITH_KNEE = frozenset({Level.KNEE_DISARTICULATION, Level.TRANSFEMORAL, Level.HIP_DISARTICULATION})

VA_DOD_LOWER = "lower_limb_amputation_va_dod_cpg_2024"
VA_DOD_UPPER = "upper_limb_amputation_va_dod_cpg_2022"
CMS = "lower_limb_prosthesis_cms_consensus_2017"

WEAK_FOR = "Weak for"
NEITHER = "Neither for nor against"
GRADES = (WEAK_FOR, NEITHER)  # the VA/DoD grades used here; CMS statements have none


@dataclass(frozen=True)
class ComponentInfo:
    key: str  # also the shared/i18n.py label key: "component.<key>"
    # Levels whose prosthesis has this component. For these the section is
    # listed even when no statement applies ("no source in the library").
    levels: frozenset[Level]


# In the order the review page shows them.
COMPONENTS: tuple[ComponentInfo, ...] = (
    ComponentInfo("knee", WITH_KNEE),
    ComponentInfo("foot_ankle", LOWER),
    ComponentInfo("pylon", frozenset()),  # only listed when a statement applies
    ComponentInfo("socket", LOWER),
    ComponentInfo("interface", LOWER),
    ComponentInfo("suspension", LOWER),
    ComponentInfo("prosthesis_type", UPPER),
    ComponentInfo("control_and_fit", UPPER),
)
COMPONENT_KEYS = tuple(info.key for info in COMPONENTS)


@dataclass(frozen=True)
class Rule:
    statement: GuidelineStatement
    levels: frozenset[Level]
    k_levels: Optional[frozenset[str]] = None  # shown only when one of these is recorded
    ambulators_only: bool = False  # the source speaks of ambulators: not shown for K0
    unilateral_only: bool = False


RULES: tuple[Rule, ...] = (
    # Knee unit
    Rule(
        GuidelineStatement(
            id="va_dod_ll_17_microprocessor_knee",
            component="knee",
            doc_id=VA_DOD_LOWER,
            grade=WEAK_FOR,
            quote=Quote(56, "For prosthetic ambulators, we suggest prescribing microprocessor knee "
                            "units over non-microprocessor knee units for reducing falls, optimizing "
                            "functional mobility, and improving patient satisfaction."),
            context=(
                Quote(56, "The evidence in this discussion is suggestive of the recommendation being "
                          "inclusive of most if not all patients that ambulate, and not limiting the "
                          "recommendation to just those that are classified as community ambulators."),
                Quote(56, "The Work Group’s confidence in the quality of the evidence was very low."),
            ),
        ),
        levels=WITH_KNEE,
        ambulators_only=True,
    ),
    Rule(
        GuidelineStatement(
            id="cms_k2_microprocessor_knee",
            component="knee",
            doc_id=CMS,
            grade=None,
            quote=Quote(10, "Therefore, the Workgroup acknowledges an amputee functioning at the K2 "
                            "level may benefit from MPK technology. However, as a population, these "
                            "individuals cannot be categorically defined for policy purposes."),
        ),
        levels=WITH_KNEE,
        k_levels=frozenset({"K2"}),
    ),
    # Foot and ankle
    Rule(
        GuidelineStatement(
            id="va_dod_ll_19_esar_over_sach",
            component="foot_ankle",
            doc_id=VA_DOD_LOWER,
            grade=WEAK_FOR,
            quote=Quote(57, "For prosthetic ambulators, we suggest energy storing and return (ESAR) or "
                            "microprocessor-controlled foot and ankle components over solid ankle "
                            "cushioned heel (SACH) feet to improve ambulation and patient satisfaction."),
            context=(
                Quote(58, "Subgroup considerations include prosthetic ambulators who walk household or "
                          "very limited community distances, as this population is rarely included in "
                          "the evidence limiting generalization to all prosthetic ambulators."),
                Quote(58, "The Work Group’s confidence in the quality of the evidence was very low for "
                          "three studies and low for one study, thus very low overall."),
            ),
        ),
        levels=LOWER,
        ambulators_only=True,
    ),
    Rule(
        GuidelineStatement(
            id="va_dod_ll_18_no_specific_foot",
            component="foot_ankle",
            doc_id=VA_DOD_LOWER,
            grade=NEITHER,
            quote=Quote(57, "For prosthetic ambulators, there is insufficient evidence to prescribe any "
                            "specific energy storing and return (ESAR) or microprocessor foot and ankle "
                            "component over another."),
            context=(
                Quote(58, "This finding supports clinicians trialing of a variety of energy storing and "
                          "returning prosthetic feet as part of routine clinical care to optimize "
                          "patient-centered outcomes."),
            ),
        ),
        levels=LOWER,
        ambulators_only=True,
    ),
    Rule(
        GuidelineStatement(
            id="cms_power_assist_ankle",
            component="foot_ankle",
            doc_id=CMS,
            grade=None,
            quote=Quote(11, "The Workgroup believes that at the present time, the literature does not "
                            "support coverage of the power assist ankle for Medicare beneficiaries."),
        ),
        levels=LOWER,
        ambulators_only=True,
    ),
    # Pylon
    Rule(
        GuidelineStatement(
            id="cms_k2_shock_absorbing_pylon",
            component="pylon",
            doc_id=CMS,
            grade=None,
            quote=Quote(11, "The Workgroup believes that at the present time, the literature does not "
                            "support coverage of shock absorbing pylons for Medicare beneficiaries who "
                            "utilize their prosthesis at the K2 level."),
        ),
        levels=LOWER,
        k_levels=frozenset({"K2"}),
    ),
    # Socket
    Rule(
        GuidelineStatement(
            id="va_dod_ll_15_transfemoral_socket",
            component="socket",
            doc_id=VA_DOD_LOWER,
            grade=NEITHER,
            quote=Quote(55, "For community ambulators, there is insufficient evidence to recommend any "
                            "specific transfemoral socket design."),
            context=(
                Quote(55, "Community ambulators in these studies is defined as either a self-reported "
                          "ability to ambulate a minimum of 20 minutes in the community or a clinician’s "
                          "assessment including use of the Amputee Mobility Predictor with Prosthesis "
                          "functional outcome measure."),
                Quote(55, "These studies support clinicians trialing of a variety of prosthetic socket "
                          "designs."),
            ),
        ),
        levels=frozenset({Level.TRANSFEMORAL}),
        ambulators_only=True,
    ),
    Rule(
        GuidelineStatement(
            id="va_dod_ll_16_ischial_containment",
            component="socket",
            doc_id=VA_DOD_LOWER,
            grade=NEITHER,
            quote=Quote(55, "For community ambulators, there is insufficient evidence to recommend for or "
                            "against ischial containment or sub-ischial socket designs."),
        ),
        levels=frozenset({Level.TRANSFEMORAL}),
        ambulators_only=True,
    ),
    # Interface (liner / socket insert)
    Rule(
        GuidelineStatement(
            id="cms_interface_material",
            component="interface",
            doc_id=CMS,
            grade=None,
            quote=Quote(11, "The Workgroup has found no evidence to direct the choice of interface "
                            "material between prosthesis and skin. Instead the Workgroup believes this is "
                            "a decision which is individualized based on various characteristics of the "
                            "beneficiary, including: the physical condition of the residual limb and the "
                            "patient’s hand/upper extremity function, as well as the activity level, "
                            "suspension, comfort and limb/skin protection provided by the material and "
                            "needed by the user."),
        ),
        levels=LOWER,
    ),
    # Suspension
    Rule(
        GuidelineStatement(
            id="cms_multiple_suspension",
            component="suspension",
            doc_id=CMS,
            grade=None,
            quote=Quote(11, "There is no evidence found by the Workgroup on the use of ‘multiple suspension "
                            "systems’ in the prosthetic leg of a single individual. The Workgroup believes "
                            "that multiple suspension systems (e.g., supracondylar suspension plus pin "
                            "suspension; belt suspension plus pin suspension) may be complimentary in "
                            "order to maintain adequate suspension and alignment of a prosthetic leg."),
        ),
        levels=LOWER,
    ),
    Rule(
        GuidelineStatement(
            id="cms_elevated_vacuum",
            component="suspension",
            doc_id=CMS,
            grade=None,
            quote=Quote(12, "The Workgroup believes that though some physiologic benefits are exhibited by "
                            "the use of elevated vacuum suspension systems (for example, stabilization of "
                            "limb volume and decreased pistoning), the current literature does not support "
                            "improved functional health outcomes with the use of this component."),
        ),
        levels=LOWER,
    ),
    # Upper limb: type of prosthesis
    Rule(
        GuidelineStatement(
            id="va_dod_ul_7_body_or_externally_powered",
            component="prosthesis_type",
            doc_id=VA_DOD_UPPER,
            grade=WEAK_FOR,
            quote=Quote(31, "For patients with major unilateral upper limb amputation (i.e., through or "
                            "proximal to the wrist), we suggest use of a body-powered or externally "
                            "powered prosthesis to improve independence and reduce disability."),
            context=(
                Quote(31, "However, there was no evidence in the systematic evidence review to recommend "
                          "one type of prosthetic system over another."),
                Quote(32, "VA/DoD best-practice has recognized that prescriptions for upper extremity "
                          "prostheses should be based on a collaborative decision between the patient "
                          "and the care team."),
                Quote(32, "The Work Group’s confidence in the quality of the evidence was very low and the "
                          "body of evidence is limited."),
            ),
        ),
        levels=MAJOR_UPPER,
        unilateral_only=True,
    ),
    # Upper limb: control strategy, socket, suspension, components
    Rule(
        GuidelineStatement(
            id="va_dod_ul_8_no_specific_component",
            component="control_and_fit",
            doc_id=VA_DOD_UPPER,
            grade=NEITHER,
            quote=Quote(32, "There is insufficient evidence to recommend for or against any specific "
                            "control strategy, socket design, suspension method, or component."),
            context=(
                Quote(32, "One of the challenges in addressing this topic is that each prosthesis is "
                          "custom-made for the patient based on their level of amputation, goals, needs, "
                          "and specific anatomy."),
            ),
        ),
        levels=UPPER,
    ),
)


# Functional level: the CMS descriptions of K0-K4 (the brief's "analysis of
# functional requirements"). Only the opening sentence of each level; the
# lists of tasks that follow are on the same pages.
def _k_level(level: str, page: int, text: str) -> GuidelineStatement:
    return GuidelineStatement(f"cms_{level.lower()}_description", "functional_level", CMS, None,
                              Quote(page, text))


K_LEVEL_DESCRIPTIONS: dict[str, GuidelineStatement] = {
    "K0": _k_level("K0", 4, "Level 0: Does not have the ability or potential to ambulate or transfer "
                            "safely with or without assistance and a prosthesis does not enhance their "
                            "quality of life or mobility."),
    "K1": _k_level("K1", 4, "Level 1: Has the ability or potential to use a prosthesis for transfers or "
                            "ambulation on level surfaces at fixed cadence, typical of the limited and "
                            "unlimited household ambulator."),
    "K2": _k_level("K2", 5, "Level 2: Has the ability or potential for ambulation with the ability to "
                            "transverse low level environmental barriers such as curbs, stairs or uneven "
                            "surfaces. This level is typical of the limited community ambulator."),
    "K3": _k_level("K3", 5, "Level 3: Has the ability or potential for ambulation with variable cadence, "
                            "typical of the community ambulator who has the ability to transverse most "
                            "environmental barriers and may have vocational, therapeutic, or exercise "
                            "activity that demands prosthetic utilization beyond simple locomotion."),
    "K4": _k_level("K4", 6, "Level 4: Has the ability or potential for prosthetic ambulation that exceeds "
                            "the basic ambulation skills, exhibiting high impact, stress or energy levels "
                            "typical of the prosthetic demands of the child, active adult, or athlete."),
}

# Shown with every K-level: what the source says K-levels are and are not.
K_LEVEL_CAUTIONS: tuple[GuidelineStatement, ...] = (
    GuidelineStatement(
        "cms_k_level_intended_use", "functional_level", CMS, None,
        Quote(9, "As previously noted, the K level classification should not be considered a functional "
                 "classification; instead it is a description of the intended use of the prosthesis."),
    ),
    GuidelineStatement(
        "cms_k_level_research_gap", "functional_level", CMS, None,
        Quote(6, "The Workgroup has further determined that research to-date has failed to connect a "
                 "patient’s medical condition (e.g. strength, ROM, balance, etc.), functional abilities, "
                 "or outcome measure results to his/her K level."),
    ),
)

ALL_STATEMENTS: tuple[GuidelineStatement, ...] = (
    *(rule.statement for rule in RULES),
    *K_LEVEL_DESCRIPTIONS.values(),
    *K_LEVEL_CAUTIONS,
)
