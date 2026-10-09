"""What the sources in the library say about prosthetic design and fitting.

The brief's prosthetics domain ends with "design and fit". This holds, in
the same form as reasoning/component_guide.py, statements on:
- readiness: who is ready for fitting, who needs preparation first,
- prosthesis_stage: preparatory (interim) or definitive prosthesis,
- fitting: the fitting steps, check-out and follow-up,
- alignment: what alignment is, and what an alignment error may cause.
Socket, interface and suspension design are prescription choices and stay
with the components in reasoning/component_guide.py.

Each statement is copied word for word with its page; who it applies to
comes only from the source's own wording (component_guide.py's docstring
lists the rules). The sources:
- ICRC, Prosthetic Gait Analysis for Physiotherapists (2014): a training
  manual for ICRC programmes, about lower-limb prostheses, with sections
  marked TT (transtibial) and TF (transfemoral). It gives no grades.
- VA/DoD lower limb (2024): recommendation 5 and the algorithm (module B).
- VA/DoD upper limb (2022): phases of care and tables 5 and 6.
- CMS consensus (2017): preparatory versus definitive prosthesis.
- WHO standards for prosthetics and orthotics, implementation manual
  (2017): service delivery steps, for prostheses and orthoses at any level.

tests/test_component_guide.py checks every quote, and every list item, on
its page in data/extracted/<doc_id>.txt.
"""

from reasoning.component_guide import (
    ALL_LEVELS,
    CMS,
    ICRC,
    LOWER,
    TF,
    TT,
    UPPER,
    VA_DOD_LOWER,
    VA_DOD_UPPER,
    WEAK_FOR,
    WHO_MANUAL,
    ComponentInfo,
    Rule,
)
from reasoning.models import GuidelineStatement, Quote

# In the order the review page shows them. Every case gets every section,
# with "no statement in the source library" where none applies.
SECTIONS: tuple[ComponentInfo, ...] = (
    ComponentInfo("readiness", ALL_LEVELS),
    ComponentInfo("prosthesis_stage", ALL_LEVELS),
    ComponentInfo("fitting", ALL_LEVELS),
    ComponentInfo("alignment", ALL_LEVELS),
)
SECTION_KEYS = tuple(info.key for info in SECTIONS)

# The intake fields that readiness statements speak about (wounds and
# infection, oedema and volume, skin and scars, pain, sensation, general
# and cognitive condition). The review page shows what the case recorded
# for each, next to the statements; it never judges readiness itself.
READINESS_FIELDS = (
    "months_since_amputation",
    "residual_limb.wound_status",
    "residual_limb.volume_stability",
    "residual_limb.skin_condition",
    "residual_limb.pain",
    "residual_limb.sensation",
    "comorbidities",
    "cognitive_status",
)


def _icrc(id: str, section: str, quote: Quote, *context: Quote) -> GuidelineStatement:
    return GuidelineStatement(id, section, ICRC, None, quote, context)


RULES: tuple[Rule, ...] = (
    # Readiness
    Rule(
        _icrc("icrc_ready_for_fitting", "readiness",
              Quote(49, "Those who are ready for fitting", items=(
                  "Free of pain and infection;", "No oedema;", "Minimal contracture;",
                  "Non-adherent scar tissue;", "No open wounds;", "No muscle weakness;",
                  "Intact skin;", "Good general condition.",
              )),
              Quote(49, "There is no general rule about whether or not to fit an amputee with a "
                        "prosthesis. Each case must be assessed on an individual basis, with questions "
                        "being asked about the possibility, the usefulness and the harmlessness of fitting "
                        "a prosthesis.")),
        levels=LOWER,
    ),
    Rule(
        _icrc("icrc_needs_preparatory_treatment", "readiness",
              Quote(49, "Those who need preparatory treatment before fitting", items=(
                  "Profuse oedema;", "Contractures in extreme ranges;", "Adherent scar tissue;",
                  "Open wounds;", "Bad hygiene;", "Neuromas;", "Bone spurs;", "Muscle weakness;",
                  "Phantom sensation/pain;", "Skin conditions such as anaerobic infections.",
              ))),
        levels=LOWER,
    ),
    Rule(
        _icrc("icrc_cannot_be_fitted", "readiness",
              Quote(49, "Those who cannot be fitted", items=(
                  "The amputee’s physical or mental condition is not appropriate for fitting;",
                  "It is technically not possible to fit a prosthesis.",
              )),
              Quote(49, "Amputees who cannot be fitted with prostheses can gain independence by using a "
                        "wheelchair or with the support of technical aids.")),
        levels=LOWER,
    ),
    Rule(
        _icrc("icrc_tt_knee_flexion_contracture", "readiness",
              Quote(46, "TT: Knee flexion contracture of 10° or less can be treated conservatively. Knee "
                        "flexion contracture of 25° or more may require a bent-knee prosthesis.")),
        levels=TT,
    ),
    Rule(
        GuidelineStatement(
            id="va_dod_ll_5_rigid_dressing",
            component="readiness",
            doc_id=VA_DOD_LOWER,
            grade=WEAK_FOR,
            quote=Quote(36, "Post-transtibial amputation, we suggest application of a rigid or semi-rigid "
                            "residual limb dressing to promote healing and early prosthesis use as soon as "
                            "feasible."),
            context=(
                Quote(38, "For the main comparison of rigid dressings to soft dressings, the SR found that "
                          "the time from amputation to wound healing or prosthesis readiness was shorter in "
                          "patients with rigid or semirigid dressing than with soft dressing, albeit with very "
                          "low certainty of evidence."),
                Quote(38, "The Work Group’s confidence in the quality of the evidence overall was very low."),
            ),
        ),
        levels=TT,
    ),
    Rule(
        GuidelineStatement(
            id="va_dod_ul_cleared_for_socket_fitting",
            component="readiness",
            doc_id=VA_DOD_UPPER,
            grade=None,
            quote=Quote(17, "The patient must be medically, surgically, and cognitively cleared by the care "
                            "team for a diagnostic socket fitting to occur."),
            context=(
                Quote(17, "The goal of the pre-prosthetic phase is to prepare the patient and his or her "
                          "residual limb for initial prosthetic fitting."),
                Quote(17, "The end of the perioperative phase occurs when residual limb incisions are closed "
                          "and free of infection, sutures are removed, self-care activities of daily living "
                          "(ADL) using one-handed strategies and adaptive or durable medical equipment are "
                          "progressing, and the patient has been medically cleared for further "
                          "rehabilitation."),
            ),
        ),
        levels=UPPER,
    ),
    Rule(
        GuidelineStatement(
            id="who_preparatory_training",
            component="readiness",
            doc_id=WHO_MANUAL,
            grade=None,
            quote=Quote(101, "Many users have to undergo preparatory training to strengthen their muscles and "
                             "increase the range of movement in their joints before a prosthesis or orthosis "
                             "can be fitted."),
            context=(
                Quote(102, "The aim of preparatory training is to ensure that individuals are physically "
                           "ready for the prosthesis or orthosis fitting."),
            ),
        ),
        levels=ALL_LEVELS,
    ),
    Rule(
        GuidelineStatement(
            id="who_decision_not_to_prescribe",
            component="readiness",
            doc_id=WHO_MANUAL,
            grade=None,
            quote=Quote(100, "Some assessments lead to a decision not to prescribe a prosthesis or orthosis, "
                             "for example, if it is deemed that the fitting is not viable or would not benefit "
                             "the user. The reasons should be fully explained and justified to the user and "
                             "caregivers and an alternative treatment plan proposed, such as prescription of "
                             "a wheelchair or therapy."),
        ),
        levels=ALL_LEVELS,
    ),
    # Preparatory (interim) or definitive prosthesis
    Rule(
        GuidelineStatement(
            id="cms_preparatory_vs_definitive",
            component="prosthesis_stage",
            doc_id=CMS,
            grade=None,
            quote=Quote(10, "There is no evidence found by the Workgroup to define best practices regarding "
                            "the prescription of a preparatory versus a definitive prosthesis to an individual "
                            "with a new amputation. Therefore, it is expected that based on patient "
                            "characteristics, the team of professionals evaluating the patient will make an "
                            "appropriate decision regarding these needs."),
        ),
        levels=LOWER,
    ),
    Rule(
        GuidelineStatement(
            id="cms_non_alignable_preparatory",
            component="prosthesis_stage",
            doc_id=CMS,
            grade=None,
            quote=Quote(10, "However it is to be noted that the Workgroup does not recommend the use of "
                            "non-alignable preparatory prosthetics [L5500 – L5600]."),
        ),
        levels=LOWER,
    ),
    Rule(
        _icrc("icrc_definitive_socket_stable_stump", "prosthesis_stage",
              Quote(44, "A definitive socket is fitted to a stable stump. If the stump still has oedema, it "
                        "will quickly reduce its volume after the fitting, with the result that the socket "
                        "becomes too wide, creating unnecessary difficulties in the socket fit.")),
        levels=LOWER,
    ),
    Rule(
        _icrc("icrc_stump_shrinkage_recasting", "prosthesis_stage",
              Quote(46, "First-time users should be made aware of the stump “shrinkage” in the initial "
                        "stage, which is normal and can be easily managed by using additional layers of "
                        "socks. However, a recasting could be suggested if more than two layers of socks are "
                        "needed.")),
        levels=LOWER,
    ),
    Rule(
        _icrc("icrc_bilateral_tf_stubbies", "prosthesis_stage",
              Quote(48, "Bilateral TF amputees can temporally be fitted with shortened prostheses called "
                        "“stubbies.”"),
              Quote(48, "These prostheses are most effective for amputees with short stumps. They are used "
                        "for therapy until the amputee gains confidence and is able to use “normal length” "
                        "prostheses.")),
        levels=TF,
        bilateral_only=True,
    ),
    Rule(
        GuidelineStatement(
            id="va_dod_ul_prescription_elements",
            component="prosthesis_stage",
            doc_id=VA_DOD_UPPER,
            grade=None,
            quote=Quote(18, "Comprehensive prescription for an upper limb prosthesis should include:", items=(
                "Design (e.g., preparatory versus definitive)",
                "Control strategy (e.g., passive, externally powered, body powered, task specific)",
                "The anatomical side and amputation level of the prosthesis",
                "Type of socket interface (e.g., soft insert, elastomer liner, flexible thermoplastic)",
                "Type of socket frame (e.g., thermoplastic or laminated)",
                "Suspension mechanism (e.g., harness, suction, anatomical)",
                "Terminal device (TD)",
                "Wrist unit (if applicable)",
                "Elbow unit (if applicable)",
                "Shoulder unit (if applicable)",
            )),
        ),
        levels=UPPER,
    ),
    # Fitting, check-out and follow-up
    Rule(
        GuidelineStatement(
            id="va_dod_ll_algorithm_fitting",
            component="fitting",
            doc_id=VA_DOD_LOWER,
            grade=None,
            quote=Quote(144, "Initiate lower limb prosthetic fabrication, fitting, and delivery."),
            context=(
                Quote(144, "Is the patient a candidate for a prosthesis OR pre-prosthetic training?"),
                Quote(144, "Develop prosthetic prescription including all necessary components."),
                Quote(144, "Conduct final prosthesis check out including all appropriate members of the "
                           "care team."),
                Quote(145, "Does the prosthetic device improve functional statis and meet realistic patient "
                           "goals?"),
            ),
        ),
        levels=LOWER,
    ),
    Rule(
        _icrc("icrc_socket_fit_and_alignment_most_important", "fitting",
              Quote(66, "Regardless of the functions provided by even the most sophisticated mechanical "
                        "devices, the most important factors in the usefulness of an artificial leg are the "
                        "socket fitting and the alignment of the various parts with the body and with each "
                        "other."),
              Quote(66, "Fitting affects alignment, alignment affects fitting, and both affect comfort and "
                        "function."),
              Quote(65, "It does not aim to cover fully the complexity of fitting prostheses but rather sets "
                        "out to address the main issues that need to be resolved before to proceeding to "
                        "post-fitting rehabilitation.")),
        levels=LOWER,
    ),
    Rule(
        _icrc("icrc_structured_fitting_process", "fitting",
              Quote(66, "In order to assure the best possible outcome of dynamic alignment and gait "
                        "training, it is recommended that the physiotherapist repeat the same structured "
                        "process followed by the prosthetist during static and dynamic fitting:", items=(
                            "Explain the process to the amputee;", "Re-examine the amputee;",
                            "Re-examine the stump;", "Check the prosthesis prescription;",
                            "Check the prosthesis.",
                        ))),
        levels=LOWER,
    ),
    Rule(
        _icrc("icrc_tf_check_socket", "fitting",
              Quote(73, "Sometimes P&O technicians will use a “check socket” in order to make sure that the "
                        "socket fits (see picture).")),
        levels=TF,
    ),
    Rule(
        _icrc("icrc_tf_prosthesis_length", "fitting",
              Quote(72, "A prosthesis that is too long may cause abducted gait, lateral trunk bending towards "
                        "the sound leg, vaulting and circumduction. A prosthesis that is too short may cause "
                        "lateral trunk bending towards the prosthetic side."),
              Quote(72, "Is the device of the correct length (no more than 10 mm shorter than the sound "
                        "leg)?")),
        levels=TF,
    ),
    Rule(
        GuidelineStatement(
            id="who_delivery_check",
            component="fitting",
            doc_id=WHO_MANUAL,
            grade=None,
            quote=Quote(102, "Once the fit, function and comfort of the prosthesis or orthosis is deemed "
                             "optimal and the user is confident in its use, all its features should be checked "
                             "thoroughly by the responsible prosthetics and orthotics clinician before it is "
                             "finalized. Users and caregivers should have the final say on the acceptability of "
                             "fit, function and appearance."),
        ),
        levels=ALL_LEVELS,
    ),
    Rule(
        GuidelineStatement(
            id="va_dod_ul_signs_prosthesis_needs_modification",
            component="fitting",
            doc_id=VA_DOD_UPPER,
            grade=None,
            quote=Quote(18, "Patients who use a prosthesis should be advised to report any of the following "
                            "symptoms:", items=(
                                "Ongoing pain in the residual limb or associated with a prosthetic harness",
                                "Skin breakdown",
                                "Change in the ability to don and doff the prosthesis",
                                "Change in limb volume (weight gain or loss)",
                                "Change in pattern of usage",
                            )),
        ),
        levels=UPPER,
    ),
    # Alignment
    Rule(
        _icrc("icrc_alignment_definition", "alignment",
              Quote(31, "Alignment is the establishment of the position in space of the components of the "
                        "prosthesis relative to each other and to the amputee."),
              Quote(31, "Appropriate prosthetic alignment involves several steps:", items=(
                  "Initial/bench alignment (alignment done on the bench);",
                  "Static fitting (amputee standing/sitting);",
                  "Static alignment (on amputee);",
                  "Balance and weight-bearing exercises;",
                  "Dynamic alignment (amputee walking);",
                  "Gait training;",
                  "Alignment corrections.",
              ))),
        levels=LOWER,
    ),
    Rule(
        _icrc("icrc_tt_initial_alignment", "alignment",
              Quote(31, "Initial alignment for transtibial prostheses is carried out in the workshop and in "
                        "accordance with a protocol and the manufacturer’s guidelines (which differ depending "
                        "on the components used). Stump conditions (length and position) also have to be "
                        "taken into consideration."),
              Quote(35, "The concept of heel and toe levers is helpful to understand support stability in TT "
                        "amputees. A longer heel lever tends to destabilize the limb, while a longer toe lever "
                        "improves stability.")),
        levels=TT,
    ),
    Rule(
        _icrc("icrc_tt_foot_angle", "alignment",
              Quote(68, "Excessive dorsiflexion of the prosthetic foot may cause excessive knee flexion or "
                        "drop off. Conversely, excessive plantar flexion of the prosthetic foot may cause "
                        "absent or insufficient knee flexion, delayed knee flexion, flat foot or "
                        "circumduction.")),
        levels=TT,
    ),
    Rule(
        _icrc("icrc_tt_socket_flexion", "alignment",
              Quote(68, "Too much flexion in the socket may cause early knee flexion or excessive knee "
                        "flexion. Conversely, too much extension in the socket may cause delayed knee "
                        "flexion.")),
        levels=TT,
    ),
    Rule(
        _icrc("icrc_tt_foot_position", "alignment",
              Quote(68, "If the foot is too far posterior in relation to the socket or too small, it may "
                        "cause excessive knee flexion or early knee flexion (drop off). Conversely, if the "
                        "foot is too far anterior in relation to the socket or too big, it may cause absent, "
                        "insufficient or delayed knee flexion. On the other hand, excessive medial placement "
                        "of the foot may cause excessive lateral shift of the prosthesis.")),
        levels=TT,
    ),
    Rule(
        _icrc("icrc_tf_initial_alignment", "alignment",
              Quote(36, "Initial bench alignment for transfemoral prostheses is carried out in the workshop "
                        "and in accordance with a protocol and the manufacturer’s guidelines (which differ "
                        "depending on the components used). Stump conditions (length and position) also have "
                        "to be taken into consideration."),
              Quote(41, "The stability of the prosthetic knee is also influenced by the relative length of "
                        "heel and toe levers and the joint itself can be attached more posteriorly (for "
                        "improved stability) or anteriorly (for added control). TF amputees have the "
                        "additional challenge of controlling a prosthetic knee unit.")),
        levels=TF,
    ),
    Rule(
        _icrc("icrc_tf_socket_angles", "alignment",
              Quote(71, "Initial socket flexion that is insufficient to give hip extensors a biomechanical "
                        "advantage may cause knee instability, excessive lumbar lordosis and uneven step "
                        "length."),
              Quote(71, "Insufficient socket adduction may cause lateral trunk bending.")),
        levels=TF,
    ),
    Rule(
        _icrc("icrc_tf_foot_position", "alignment",
              Quote(71, "Excessive foot outset may cause lateral trunk bending. If the foot is too posterior "
                        "in relation to the tube or too small, this may cause drop off. Conversely, a foot "
                        "that is too anterior in relation to the tube or too big may cause pelvic rise."),
              Quote(71, "Too much plantar flexion may cause knee instability.")),
        levels=TF,
    ),
    Rule(
        _icrc("icrc_tf_knee_axis", "alignment",
              Quote(71, "If the knee is set too anterior, it may cause knee instability. Conversely, a "
                        "prosthesis that has been aligned with too much stability may cause delayed knee "
                        "flexion or circumduction. A knee axis in excessive external rotation may cause "
                        "medial whip. Conversely, knee axis in excessive internal rotation may cause lateral "
                        "whip. A knee axis that is not horizontal and perpendicular to the line of "
                        "progression causes circumduction.")),
        levels=TF,
    ),
    Rule(
        _icrc("icrc_tf_knee_friction", "alignment",
              Quote(71, "Excessive friction in the knee may cause insufficient heel rise in swing, "
                        "circumduction, delayed knee flexion or vaulting. Conversely, insufficient friction in "
                        "the knee may cause excessive heel rise in swing, vaulting, terminal impact, uneven "
                        "step length and uneven timing.")),
        levels=TF,
    ),
    Rule(
        _icrc("icrc_footwear_alters_alignment", "alignment",
              Quote(110, "Amputees will be made aware that footwear and heel height can alter the alignment "
                         "of the prosthesis, which in turn affects the gait pattern, the lumbar spine, etc. The "
                         "height of the heel of the shoe must remain as fitted for the prosthesis and should "
                         "not be changed.")),
        levels=LOWER,
    ),
    Rule(
        GuidelineStatement(
            id="who_fit_and_alignment_customization",
            component="alignment",
            doc_id=WHO_MANUAL,
            grade=None,
            quote=Quote(101, "Individual customization is required for fit and alignment in order to achieve "
                             "optimum comfort, function and appearance, thus ensuring that the product can be "
                             "used effectively."),
        ),
        levels=ALL_LEVELS,
    ),
)

ALL_STATEMENTS: tuple[GuidelineStatement, ...] = tuple(rule.statement for rule in RULES)
