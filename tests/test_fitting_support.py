"""Tests for reasoning/fitting_support.py: which design and fitting statements a case gets."""

import unittest

from reasoning.fitting_guide import READINESS_FIELDS, RULES, SECTION_KEYS
from reasoning.fitting_support import fitting_support
from shared.case_schema import ActivityProfile, AmputationLevel, Case, ResidualLimb, VolumeStability, WoundStatus


def make_case(level: str, side: str = "left", **fields) -> Case:
    return Case(amputation_level=level, side=side, **fields)


def shown(support) -> dict[str, list[str]]:
    """section -> ids of the statements shown in it."""
    return {section.component: [c.statement.id for c in section.statements] for section in support.sections}


def ids(support) -> set[str]:
    return {c.statement.id for c in support.statements}


class LowerLimbTests(unittest.TestCase):
    def test_transtibial(self):
        sections = shown(fitting_support(make_case("transtibial")))
        self.assertEqual(list(sections), list(SECTION_KEYS))
        self.assertEqual(sections["readiness"], [
            "icrc_ready_for_fitting", "icrc_needs_preparatory_treatment", "icrc_cannot_be_fitted",
            "icrc_tt_knee_flexion_contracture", "va_dod_ll_5_rigid_dressing",
            "who_preparatory_training", "who_decision_not_to_prescribe",
        ])
        self.assertEqual(sections["prosthesis_stage"], [
            "cms_preparatory_vs_definitive", "cms_non_alignable_preparatory",
            "icrc_definitive_socket_stable_stump", "icrc_stump_shrinkage_recasting",
        ])
        self.assertEqual(sections["alignment"], [
            "icrc_alignment_definition", "icrc_tt_initial_alignment", "icrc_tt_foot_angle",
            "icrc_tt_socket_flexion", "icrc_tt_foot_position", "icrc_footwear_alters_alignment",
            "who_fit_and_alignment_customization",
        ])

    def test_tt_and_tf_statements_only_at_their_level(self):
        tt = ids(fitting_support(make_case("transtibial")))
        tf = ids(fitting_support(make_case("transfemoral")))
        for level in ("partial_foot", "syme", "knee_disarticulation", "hip_disarticulation"):
            with self.subTest(level=level):
                other = ids(fitting_support(make_case(level)))
                self.assertFalse({i for i in other if "_tt_" in i or "_tf_" in i})
                self.assertIn("icrc_ready_for_fitting", other)  # lower limb, any level
        self.assertTrue({"icrc_tt_foot_angle", "va_dod_ll_5_rigid_dressing"} <= tt - tf)
        self.assertTrue({"icrc_tf_knee_axis", "icrc_tf_check_socket"} <= tf - tt)

    def test_stubbies_only_bilateral_transfemoral(self):
        self.assertIn("icrc_bilateral_tf_stubbies", ids(fitting_support(make_case("transfemoral", "bilateral"))))
        self.assertNotIn("icrc_bilateral_tf_stubbies", ids(fitting_support(make_case("transfemoral"))))
        self.assertNotIn("icrc_bilateral_tf_stubbies",
                         ids(fitting_support(make_case("transtibial", "bilateral"))))

    def test_k_level_does_not_change_fitting_statements(self):
        # None of these sources limits a statement to a K-level or to ambulators.
        base = ids(fitting_support(make_case("transfemoral")))
        for k_level in ("K0", "K2", "K4"):
            with self.subTest(k_level=k_level):
                case = make_case("transfemoral", activity=ActivityProfile(k_level=k_level))
                self.assertEqual(ids(fitting_support(case)), base)


class UpperLimbTests(unittest.TestCase):
    def test_transradial(self):
        self.assertEqual(shown(fitting_support(make_case("transradial"))), {
            "readiness": ["va_dod_ul_cleared_for_socket_fitting", "who_preparatory_training",
                          "who_decision_not_to_prescribe"],
            "prosthesis_stage": ["va_dod_ul_prescription_elements"],
            "fitting": ["who_delivery_check", "va_dod_ul_signs_prosthesis_needs_modification"],
            "alignment": ["who_fit_and_alignment_customization"],
        })

    def test_no_lower_limb_source(self):
        for level in ("partial_hand", "transhumeral", "shoulder_disarticulation"):
            with self.subTest(level=level):
                self.assertFalse({c.statement.doc_id for c in fitting_support(make_case(level)).statements}
                                 & {"prosthetic_gait_analysis_icrc_manual_2014",
                                    "lower_limb_amputation_va_dod_cpg_2024",
                                    "lower_limb_prosthesis_cms_consensus_2017"})


class RecordedTests(unittest.TestCase):
    def test_recorded_values_as_entered(self):
        case = make_case("transtibial", months_since_amputation=3, comorbidities=[],
                         residual_limb=ResidualLimb(wound_status="healing", volume_stability="fluctuating",
                                                    pain="phantom pain at night"))
        recorded = dict(fitting_support(case).recorded)
        self.assertEqual(list(recorded), list(READINESS_FIELDS))
        self.assertEqual(recorded["months_since_amputation"], 3)
        self.assertIs(recorded["residual_limb.wound_status"], WoundStatus.HEALING)
        self.assertIs(recorded["residual_limb.volume_stability"], VolumeStability.FLUCTUATING)
        self.assertEqual(recorded["residual_limb.pain"], "phantom pain at night")
        self.assertEqual(recorded["comorbidities"], [])
        self.assertIsNone(recorded["cognitive_status"])

    def test_statements_do_not_depend_on_recorded_values(self):
        # The page shows values next to the statements; it never picks statements by them.
        empty = ids(fitting_support(make_case("transtibial")))
        filled = make_case("transtibial", residual_limb=ResidualLimb(wound_status="open"))
        self.assertEqual(ids(fitting_support(filled)), empty)


class EveryCaseTests(unittest.TestCase):
    def test_only_guide_statements_and_every_rule_reachable(self):
        guide_ids = {rule.statement.id for rule in RULES}
        seen = set()
        for level in AmputationLevel:
            for side in ("left", "bilateral"):
                support = fitting_support(make_case(level, side))
                found = [c.statement.id for c in support.statements]
                self.assertLessEqual(set(found), guide_ids)
                self.assertEqual(len(found), len(set(found)))
                self.assertEqual([s.component for s in support.sections], list(SECTION_KEYS))
                seen.update(found)
        self.assertEqual(seen, guide_ids)


if __name__ == "__main__":
    unittest.main()
