"""Tests for reasoning/component_support.py: which guideline statements a case gets."""

import unittest

from reasoning.component_guide import RULES
from reasoning.component_support import NOTE_K0, NOTE_K_NOT_RECORDED, component_support
from shared.case_schema import ActivityProfile, Case


def make_case(level: str, k_level=None, side: str = "left", **activity) -> Case:
    return Case(amputation_level=level, side=side,
                activity=ActivityProfile(k_level=k_level, **activity))


def shown(support) -> dict[str, list[str]]:
    """component -> ids of the statements shown for it."""
    return {section.component: [c.statement.id for c in section.statements]
            for section in support.sections}


class LowerLimbTests(unittest.TestCase):
    def test_transtibial_k3(self):
        support = component_support(make_case("transtibial", "K3"))
        self.assertEqual(shown(support), {
            "foot_ankle": ["va_dod_ll_19_esar_over_sach", "va_dod_ll_18_no_specific_foot",
                           "cms_power_assist_ankle"],
            # Only the ICRC manual describes transtibial sockets ("TT" in its text).
            "socket": ["icrc_tt_ptb_socket", "icrc_tt_total_surface_bearing_socket",
                       "icrc_total_contact_socket_conditions"],
            "interface": ["cms_interface_material", "icrc_grafted_skin_interface"],
            "suspension": ["cms_multiple_suspension", "cms_elevated_vacuum", "icrc_tt_suspension_methods"],
        })
        self.assertEqual(support.notes, [])

    def test_transfemoral_k2_gets_the_k2_statements(self):
        sections = shown(component_support(make_case("transfemoral", "K2")))
        self.assertEqual(sections["knee"], ["va_dod_ll_17_microprocessor_knee", "cms_k2_microprocessor_knee",
                                            "icrc_tf_hip_flexion_contracture_knee"])
        self.assertEqual(sections["pylon"], ["cms_k2_shock_absorbing_pylon"])
        self.assertEqual(sections["socket"], ["va_dod_ll_15_transfemoral_socket",
                                              "va_dod_ll_16_ischial_containment",
                                              "icrc_total_contact_socket_conditions"])
        self.assertEqual(list(sections), ["knee", "foot_ankle", "pylon", "socket", "interface", "suspension"])

    def test_icrc_tt_and_tf_statements_only_at_their_level(self):
        tt = {c.statement.id for c in component_support(make_case("transtibial", "K3")).statements}
        tf = {c.statement.id for c in component_support(make_case("transfemoral", "K3")).statements}
        kd = {c.statement.id for c in component_support(make_case("knee_disarticulation", "K3")).statements}
        self.assertIn("icrc_tt_suspension_methods", tt)
        self.assertNotIn("icrc_tt_suspension_methods", tf | kd)
        self.assertIn("icrc_tf_hip_flexion_contracture_knee", tf)
        self.assertNotIn("icrc_tf_hip_flexion_contracture_knee", tt | kd)

    def test_k2_statements_need_k2(self):
        for k_level in ("K1", "K3", "K4", "unknown", None):
            with self.subTest(k_level=k_level):
                sections = shown(component_support(make_case("transfemoral", k_level)))
                self.assertNotIn("pylon", sections)
                self.assertNotIn("cms_k2_microprocessor_knee", sections["knee"])

    def test_k0_leaves_out_statements_about_ambulators(self):
        support = component_support(make_case("transfemoral", "K0"))
        sections = shown(support)
        # Statements that don't speak of ambulators stay.
        self.assertEqual(sections["knee"], ["icrc_tf_hip_flexion_contracture_knee"])
        self.assertEqual(sections["foot_ankle"], [])
        self.assertEqual(sections["socket"], ["icrc_total_contact_socket_conditions"])
        self.assertEqual(sections["interface"], ["cms_interface_material", "icrc_grafted_skin_interface"])
        ambulator_ids = {rule.statement.id for rule in RULES if rule.ambulators_only}
        self.assertEqual(ambulator_ids & {c.statement.id for c in support.statements}, set())
        self.assertEqual(support.notes, [NOTE_K0])

    def test_missing_k_level_noted(self):
        for k_level in (None, "unknown"):
            with self.subTest(k_level=k_level):
                support = component_support(make_case("transtibial", k_level))
                self.assertEqual(support.notes, [NOTE_K_NOT_RECORDED])
                self.assertIn("va_dod_ll_19_esar_over_sach", shown(support)["foot_ankle"])

    def test_no_knee_below_the_knee(self):
        for level in ("partial_foot", "syme", "transtibial"):
            with self.subTest(level=level):
                self.assertNotIn("knee", shown(component_support(make_case(level, "K3"))))

    def test_functional_level(self):
        support = component_support(make_case("transtibial", "K2", description="walks to the shop",
                                              functional_goals="garden again"))
        functional = support.functional
        self.assertTrue(functional.lower_limb)
        self.assertEqual(functional.k_level, "K2")
        self.assertEqual(functional.description.statement.id, "cms_k2_description")
        self.assertTrue(functional.description.statement.quote.text.startswith("Level 2:"))
        self.assertEqual(len(functional.all_levels), 5)
        self.assertEqual([c.statement.id for c in functional.cautions],
                         ["cms_k_level_intended_use", "cms_k_level_research_gap"])
        self.assertEqual((functional.activity, functional.goals), ("walks to the shop", "garden again"))
        self.assertEqual(functional.description.citation(functional.description.statement.quote),
                         "Lower Limb Prosthetic Workgroup Consensus Document (2017), p. 5")

    def test_no_k_level_no_description(self):
        functional = component_support(make_case("transtibial")).functional
        self.assertIsNone(functional.k_level)
        self.assertIsNone(functional.description)
        self.assertEqual(len(functional.all_levels), 5)  # still there for reference


class UpperLimbTests(unittest.TestCase):
    def test_transradial(self):
        support = component_support(make_case("transradial"))
        self.assertEqual(shown(support), {
            "prosthesis_type": ["va_dod_ul_7_body_or_externally_powered"],
            "control_and_fit": ["va_dod_ul_8_no_specific_component"],
        })
        self.assertEqual(support.notes, [])
        self.assertFalse(support.functional.lower_limb)
        self.assertIsNone(support.functional.description)
        self.assertEqual(support.functional.all_levels, [])

    def test_recommendation_7_only_major_unilateral(self):
        for level, side in [("partial_hand", "left"), ("transradial", "bilateral")]:
            with self.subTest(level=level, side=side):
                sections = shown(component_support(make_case(level, side=side)))
                self.assertEqual(sections["prosthesis_type"], [])  # listed, nothing applies
                self.assertEqual(sections["control_and_fit"], ["va_dod_ul_8_no_specific_component"])

    def test_k_level_ignored_for_upper_limb(self):
        support = component_support(make_case("transhumeral", "K0"))
        self.assertIsNone(support.functional.k_level)
        self.assertIn("va_dod_ul_7_body_or_externally_powered", shown(support)["prosthesis_type"])


class EveryCaseTests(unittest.TestCase):
    def test_only_guide_statements_and_every_rule_reachable(self):
        guide_ids = {rule.statement.id for rule in RULES}
        seen = set()
        for level in ("partial_foot", "syme", "transtibial", "knee_disarticulation", "transfemoral",
                      "hip_disarticulation", "partial_hand", "wrist_disarticulation", "transradial",
                      "elbow_disarticulation", "transhumeral", "shoulder_disarticulation"):
            for k_level in (None, "K0", "K1", "K2", "K3", "K4"):
                for side in ("left", "bilateral"):
                    support = component_support(make_case(level, k_level, side))
                    ids = [c.statement.id for c in support.statements]
                    self.assertLessEqual(set(ids), guide_ids)
                    self.assertEqual(len(ids), len(set(ids)))
                    seen.update(ids)
        self.assertEqual(seen, guide_ids)


if __name__ == "__main__":
    unittest.main()
