# Source inventory of the knowledge items

Facts only, for writing the evidence rule table. Built from `data/knowledge/items.json` (last changed in commit `5f45499`, 59 items) and `data/sources/catalog.json`. Documents are listed alphabetically by catalog id.

- **Component / fitting:** the item's statement is in `reasoning/component_guide.py` (component rules, K-level descriptions and cautions) or `reasoning/fitting_guide.py`.
- **Grade:** `grade_as_printed` exactly as stored; "no grade" where it is empty.
- **Page:** the page of the item's quote as numbered in a PDF viewer, from its citation.
- **Quote:** the first 120 characters of `statement` (… where it goes on). Where the statement introduces a list, the number of list items follows in brackets; the items are in `items.json`.

## Summary

| Document (catalog id) | Year | source_type | Items | Component | Fitting | Grades |
|---|---|---|---|---|---|---|
| `lower_limb_amputation_va_dod_cpg_2024` | 2024 | protocol | 7 | 5 | 2 | Neither for nor against 3, Weak for 3, no grade 1 |
| `lower_limb_prosthesis_cms_consensus_2017` | 2017 | protocol | 15 | 13 | 2 | no grade 15 |
| `prosthetic_gait_analysis_icrc_manual_2014` | 2014 | professional_knowledge | 28 | 6 | 22 | no grade 28 |
| `upper_limb_amputation_va_dod_cpg_2022` | 2022 | protocol | 5 | 2 | 3 | Neither for nor against 1, Weak for 1, no grade 3 |
| `who_po_implementation_manual_part2_2017` | 2017 | protocol | 4 | 0 | 4 | no grade 4 |
| **All** | | | **59** | **26** | **33** | Neither for nor against 4, Weak for 4, no grade 51 |

## `lower_limb_amputation_va_dod_cpg_2024`

- **Title:** VA/DoD Clinical Practice Guideline for Rehabilitation of Individuals with Lower Limb Amputation (Version 3.0)
- **Year:** 2024
- **source_type:** protocol
- **Items:** 7 (5 component, 2 fitting)
- **Grades:** Neither for nor against 3, Weak for 3, no grade 1

| knowledge_id | Part | Grade | Page | Quote (first 120 characters) |
|---|---|---|---|---|
| `va_dod_ll_17_microprocessor_knee` | component | Weak for | p. 56 | For prosthetic ambulators, we suggest prescribing microprocessor knee units over non-microprocessor knee units for reduc… |
| `va_dod_ll_19_esar_over_sach` | component | Weak for | p. 57 | For prosthetic ambulators, we suggest energy storing and return (ESAR) or microprocessor-controlled foot and ankle compo… |
| `va_dod_ll_18_no_specific_foot` | component | Neither for nor against | p. 57 | For prosthetic ambulators, there is insufficient evidence to prescribe any specific energy storing and return (ESAR) or … |
| `va_dod_ll_15_transfemoral_socket` | component | Neither for nor against | p. 55 | For community ambulators, there is insufficient evidence to recommend any specific transfemoral socket design. |
| `va_dod_ll_16_ischial_containment` | component | Neither for nor against | p. 55 | For community ambulators, there is insufficient evidence to recommend for or against ischial containment or sub-ischial … |
| `va_dod_ll_5_rigid_dressing` | fitting | Weak for | p. 36 | Post-transtibial amputation, we suggest application of a rigid or semi-rigid residual limb dressing to promote healing a… |
| `va_dod_ll_algorithm_fitting` | fitting | no grade | p. 144 | Initiate lower limb prosthetic fabrication, fitting, and delivery. |

## `lower_limb_prosthesis_cms_consensus_2017`

- **Title:** Lower Limb Prosthetic Workgroup Consensus Document
- **Year:** 2017
- **source_type:** protocol
- **Items:** 15 (13 component, 2 fitting)
- **Grades:** no grade 15

| knowledge_id | Part | Grade | Page | Quote (first 120 characters) |
|---|---|---|---|---|
| `cms_k2_microprocessor_knee` | component | no grade | p. 10 | Therefore, the Workgroup acknowledges an amputee functioning at the K2 level may benefit from MPK technology. However, a… |
| `cms_power_assist_ankle` | component | no grade | p. 11 | The Workgroup believes that at the present time, the literature does not support coverage of the power assist ankle for … |
| `cms_k2_shock_absorbing_pylon` | component | no grade | p. 11 | The Workgroup believes that at the present time, the literature does not support coverage of shock absorbing pylons for … |
| `cms_interface_material` | component | no grade | p. 11 | The Workgroup has found no evidence to direct the choice of interface material between prosthesis and skin. Instead the … |
| `cms_multiple_suspension` | component | no grade | p. 11 | There is no evidence found by the Workgroup on the use of ‘multiple suspension systems’ in the prosthetic leg of a singl… |
| `cms_elevated_vacuum` | component | no grade | p. 12 | The Workgroup believes that though some physiologic benefits are exhibited by the use of elevated vacuum suspension syst… |
| `cms_k0_description` | component | no grade | p. 4 | Level 0: Does not have the ability or potential to ambulate or transfer safely with or without assistance and a prosthes… |
| `cms_k1_description` | component | no grade | p. 4 | Level 1: Has the ability or potential to use a prosthesis for transfers or ambulation on level surfaces at fixed cadence… |
| `cms_k2_description` | component | no grade | p. 5 | Level 2: Has the ability or potential for ambulation with the ability to transverse low level environmental barriers suc… |
| `cms_k3_description` | component | no grade | p. 5 | Level 3: Has the ability or potential for ambulation with variable cadence, typical of the community ambulator who has t… |
| `cms_k4_description` | component | no grade | p. 6 | Level 4: Has the ability or potential for prosthetic ambulation that exceeds the basic ambulation skills, exhibiting hig… |
| `cms_k_level_intended_use` | component | no grade | p. 9 | As previously noted, the K level classification should not be considered a functional classification; instead it is a de… |
| `cms_k_level_research_gap` | component | no grade | p. 6 | The Workgroup has further determined that research to-date has failed to connect a patient’s medical condition (e.g. str… |
| `cms_preparatory_vs_definitive` | fitting | no grade | p. 10 | There is no evidence found by the Workgroup to define best practices regarding the prescription of a preparatory versus … |
| `cms_non_alignable_preparatory` | fitting | no grade | p. 10 | However it is to be noted that the Workgroup does not recommend the use of non-alignable preparatory prosthetics [L5500 … |

## `prosthetic_gait_analysis_icrc_manual_2014`

- **Title:** Prosthetic Gait Analysis for Physiotherapists. ICRC Physiotherapy Reference Manual
- **Year:** 2014
- **source_type:** professional_knowledge
- **Items:** 28 (6 component, 22 fitting)
- **Grades:** no grade 28

| knowledge_id | Part | Grade | Page | Quote (first 120 characters) |
|---|---|---|---|---|
| `icrc_tf_hip_flexion_contracture_knee` | component | no grade | p. 46 | TF: A hip flexion contracture contributes to knee instability and may result in the use of a lockable knee. |
| `icrc_tt_ptb_socket` | component | no grade | p. 20 | Although the socket has total contact with the stump, it concentrates force on pressure-tolerant areas and relieves forc… |
| `icrc_tt_total_surface_bearing_socket` | component | no grade | p. 20 | The total-contact socket completely encases the stump. It is designed to distribute the weight over the entire stump. Th… |
| `icrc_total_contact_socket_conditions` | component | no grade | p. 46 | A total contact socket could be the better prescription in conditions such as phantom sensations, verrucous hyperplasia\*… |
| `icrc_grafted_skin_interface` | component | no grade | p. 46 | If the skin has grafts (or burn) on the stump or under suspension, it must be carefully examined when the prosthesis is … |
| `icrc_tt_suspension_methods` | component | no grade | p. 20 | A transtibial prosthesis may be held in place in a number of different ways: [3 list items] |
| `icrc_ready_for_fitting` | fitting | no grade | p. 49 | Those who are ready for fitting [8 list items] |
| `icrc_needs_preparatory_treatment` | fitting | no grade | p. 49 | Those who need preparatory treatment before fitting [10 list items] |
| `icrc_cannot_be_fitted` | fitting | no grade | p. 49 | Those who cannot be fitted [2 list items] |
| `icrc_tt_knee_flexion_contracture` | fitting | no grade | p. 46 | TT: Knee flexion contracture of 10° or less can be treated conservatively. Knee flexion contracture of 25° or more may r… |
| `icrc_definitive_socket_stable_stump` | fitting | no grade | p. 44 | A definitive socket is fitted to a stable stump. If the stump still has oedema, it will quickly reduce its volume after … |
| `icrc_stump_shrinkage_recasting` | fitting | no grade | p. 46 | First-time users should be made aware of the stump “shrinkage” in the initial stage, which is normal and can be easily m… |
| `icrc_bilateral_tf_stubbies` | fitting | no grade | p. 48 | Bilateral TF amputees can temporally be fitted with shortened prostheses called “stubbies.” |
| `icrc_socket_fit_and_alignment_most_important` | fitting | no grade | p. 66 | Regardless of the functions provided by even the most sophisticated mechanical devices, the most important factors in th… |
| `icrc_structured_fitting_process` | fitting | no grade | p. 66 | In order to assure the best possible outcome of dynamic alignment and gait training, it is recommended that the physioth… [5 list items] |
| `icrc_tf_check_socket` | fitting | no grade | p. 73 | Sometimes P&O technicians will use a “check socket” in order to make sure that the socket fits (see picture). |
| `icrc_tf_prosthesis_length` | fitting | no grade | p. 72 | A prosthesis that is too long may cause abducted gait, lateral trunk bending towards the sound leg, vaulting and circumd… |
| `icrc_alignment_definition` | fitting | no grade | p. 31 | Alignment is the establishment of the position in space of the components of the prosthesis relative to each other and t… |
| `icrc_tt_initial_alignment` | fitting | no grade | p. 31 | Initial alignment for transtibial prostheses is carried out in the workshop and in accordance with a protocol and the ma… |
| `icrc_tt_foot_angle` | fitting | no grade | p. 68 | Excessive dorsiflexion of the prosthetic foot may cause excessive knee flexion or drop off. Conversely, excessive planta… |
| `icrc_tt_socket_flexion` | fitting | no grade | p. 68 | Too much flexion in the socket may cause early knee flexion or excessive knee flexion. Conversely, too much extension in… |
| `icrc_tt_foot_position` | fitting | no grade | p. 68 | If the foot is too far posterior in relation to the socket or too small, it may cause excessive knee flexion or early kn… |
| `icrc_tf_initial_alignment` | fitting | no grade | p. 36 | Initial bench alignment for transfemoral prostheses is carried out in the workshop and in accordance with a protocol and… |
| `icrc_tf_socket_angles` | fitting | no grade | p. 71 | Initial socket flexion that is insufficient to give hip extensors a biomechanical advantage may cause knee instability, … |
| `icrc_tf_foot_position` | fitting | no grade | p. 71 | Excessive foot outset may cause lateral trunk bending. If the foot is too posterior in relation to the tube or too small… |
| `icrc_tf_knee_axis` | fitting | no grade | p. 71 | If the knee is set too anterior, it may cause knee instability. Conversely, a prosthesis that has been aligned with too … |
| `icrc_tf_knee_friction` | fitting | no grade | p. 71 | Excessive friction in the knee may cause insufficient heel rise in swing, circumduction, delayed knee flexion or vaultin… |
| `icrc_footwear_alters_alignment` | fitting | no grade | p. 110 | Amputees will be made aware that footwear and heel height can alter the alignment of the prosthesis, which in turn affec… |

## `upper_limb_amputation_va_dod_cpg_2022`

- **Title:** VA/DoD Clinical Practice Guideline for the Management of Upper Limb Amputation Rehabilitation (Version 2.0)
- **Year:** 2022
- **source_type:** protocol
- **Items:** 5 (2 component, 3 fitting)
- **Grades:** Neither for nor against 1, Weak for 1, no grade 3

| knowledge_id | Part | Grade | Page | Quote (first 120 characters) |
|---|---|---|---|---|
| `va_dod_ul_7_body_or_externally_powered` | component | Weak for | p. 31 | For patients with major unilateral upper limb amputation (i.e., through or proximal to the wrist), we suggest use of a b… |
| `va_dod_ul_8_no_specific_component` | component | Neither for nor against | p. 32 | There is insufficient evidence to recommend for or against any specific control strategy, socket design, suspension meth… |
| `va_dod_ul_cleared_for_socket_fitting` | fitting | no grade | p. 17 | The patient must be medically, surgically, and cognitively cleared by the care team for a diagnostic socket fitting to o… |
| `va_dod_ul_prescription_elements` | fitting | no grade | p. 18 | Comprehensive prescription for an upper limb prosthesis should include: [10 list items] |
| `va_dod_ul_signs_prosthesis_needs_modification` | fitting | no grade | p. 18 | Patients who use a prosthesis should be advised to report any of the following symptoms: [5 list items] |

## `who_po_implementation_manual_part2_2017`

- **Title:** WHO standards for prosthetics and orthotics. Part 2: Implementation manual
- **Year:** 2017
- **source_type:** protocol
- **Items:** 4 (0 component, 4 fitting)
- **Grades:** no grade 4

| knowledge_id | Part | Grade | Page | Quote (first 120 characters) |
|---|---|---|---|---|
| `who_preparatory_training` | fitting | no grade | p. 101 | Many users have to undergo preparatory training to strengthen their muscles and increase the range of movement in their … |
| `who_decision_not_to_prescribe` | fitting | no grade | p. 100 | Some assessments lead to a decision not to prescribe a prosthesis or orthosis, for example, if it is deemed that the fit… |
| `who_delivery_check` | fitting | no grade | p. 102 | Once the fit, function and comfort of the prosthesis or orthosis is deemed optimal and the user is confident in its use,… |
| `who_fit_and_alignment_customization` | fitting | no grade | p. 101 | Individual customization is required for fit and alignment in order to achieve optimum comfort, function and appearance,… |
