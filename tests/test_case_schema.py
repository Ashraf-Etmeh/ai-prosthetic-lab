"""Tests for shared/case_schema.py: validation, save/load, and unrecorded fields."""

import json
import math
import unittest

from shared.case_schema import (
    ActivityLevel,
    ActivityProfile,
    AmputationLevel,
    Case,
    Etiology,
    PriorDevice,
    ResidualLimb,
    Side,
    VolumeStability,
    WoundStatus,
)


def make_case(**kwargs) -> Case:
    return Case(amputation_level=AmputationLevel.TRANSTIBIAL, side=Side.LEFT, **kwargs)


class EnumConversionTests(unittest.TestCase):
    def test_strings_become_enums(self):
        case = Case(amputation_level="transtibial", side="left", etiology="trauma")
        self.assertIs(case.amputation_level, AmputationLevel.TRANSTIBIAL)
        self.assertIs(case.side, Side.LEFT)
        self.assertIs(case.etiology, Etiology.TRAUMA)
        self.assertTrue(case.is_lower_limb)

    def test_nested_strings_become_enums(self):
        limb = ResidualLimb(wound_status="healed", volume_stability="stable")
        self.assertIs(limb.wound_status, WoundStatus.HEALED)
        self.assertIs(limb.volume_stability, VolumeStability.STABLE)
        self.assertIs(ActivityProfile(k_level="K3").k_level, ActivityLevel.K3)

    def test_none_stays_none(self):
        case = make_case()
        self.assertIsNone(case.etiology)
        self.assertIsNone(case.residual_limb.wound_status)
        self.assertIsNone(case.activity.k_level)

    def test_invalid_values_rejected(self):
        bad = {
            "amputation level": lambda: Case(amputation_level="banana", side="left"),
            "side": lambda: Case(amputation_level="syme", side="up"),
            "wound status": lambda: ResidualLimb(wound_status="bleeding"),
            "k-level": lambda: ActivityProfile(k_level="K9"),
        }
        for name, build in bad.items():
            with self.subTest(name), self.assertRaises(ValueError):
                build()


class NumberValidationTests(unittest.TestCase):
    def test_valid_numbers_accepted(self):
        case = make_case(age_years=0, months_since_amputation=0, body_weight_kg=70.5)
        self.assertEqual(case.age_years, 0)
        self.assertEqual(case.months_since_amputation, 0)
        self.assertEqual(case.body_weight_kg, 70.5)

    def test_impossible_numbers_rejected(self):
        for kwargs in [
            {"age_years": -5},
            {"months_since_amputation": -3},
            {"body_weight_kg": 0},
            {"body_weight_kg": -1},
            {"body_weight_kg": math.nan},
            {"age_years": math.inf},
        ]:
            with self.subTest(**kwargs), self.assertRaises(ValueError):
                make_case(**kwargs)

    def test_prior_device_checked(self):
        self.assertEqual(PriorDevice("old socket", years_used=0).years_used, 0)
        for kwargs in [
            {"device_description": "old socket", "years_used": -1},
            {"device_description": "old socket", "years_used": math.nan},
            {"device_description": ""},
            {"device_description": "   "},
        ]:
            with self.subTest(**kwargs), self.assertRaises(ValueError):
                PriorDevice(**kwargs)


class SerializationTests(unittest.TestCase):
    def setUp(self):
        self.case = Case(
            amputation_level=AmputationLevel.TRANSFEMORAL,
            side=Side.RIGHT,
            age_years=60,
            body_weight_kg=82.5,
            etiology=Etiology.VASCULAR,
            months_since_amputation=4,
            residual_limb=ResidualLimb(
                wound_status=WoundStatus.HEALED,
                volume_stability=VolumeStability.FLUCTUATING,
                pain="mild",
            ),
            activity=ActivityProfile(k_level=ActivityLevel.K2, functional_goals="walk to shops"),
            prior_devices=[PriorDevice(device_description="old socket", years_used=3)],
            comorbidities=["diabetes"],
        )

    def test_round_trip(self):
        self.assertEqual(Case.from_dict(self.case.to_dict()), self.case)

    def test_round_trip_through_json(self):
        saved = json.loads(json.dumps(self.case.to_dict()))
        self.assertEqual(Case.from_dict(saved), self.case)

    def test_minimal_case_round_trip(self):
        minimal = Case(amputation_level=AmputationLevel.TRANSRADIAL, side=Side.BILATERAL)
        self.assertEqual(Case.from_dict(minimal.to_dict()), minimal)

    def test_from_dict_does_not_share_lists(self):
        saved = self.case.to_dict()
        case = Case.from_dict(saved)
        saved["comorbidities"].append("added later")
        self.assertEqual(case.comorbidities, ["diabetes"])

    def test_from_dict_rejects_bad_value(self):
        with self.assertRaises(ValueError):
            Case.from_dict({**self.case.to_dict(), "side": "up"})


class UnrecordedFieldsTests(unittest.TestCase):
    def test_lower_limb_includes_leg_only_fields(self):
        missing = Case(amputation_level="transtibial", side="left").unrecorded_fields()
        self.assertIn("activity.k_level", missing)
        self.assertIn("contralateral_limb_status", missing)
        self.assertIn("residual_limb.wound_status", missing)

    def test_upper_limb_skips_leg_only_fields(self):
        missing = Case(amputation_level="transradial", side="left").unrecorded_fields()
        self.assertNotIn("activity.k_level", missing)
        self.assertNotIn("contralateral_limb_status", missing)

    def test_recorded_fields_not_listed(self):
        case = make_case(
            age_years=58,
            comorbidities=[],  # [] = asked, none reported
            residual_limb=ResidualLimb(wound_status="healed"),
        )
        missing = case.unrecorded_fields()
        self.assertNotIn("age_years", missing)
        self.assertNotIn("comorbidities", missing)
        self.assertNotIn("residual_limb.wound_status", missing)


class UnknownFieldsTests(unittest.TestCase):
    def test_unknown_answers_listed(self):
        case = make_case(
            etiology="unknown",
            residual_limb=ResidualLimb(wound_status="unknown", volume_stability="stable"),
            activity=ActivityProfile(k_level="unknown"),
        )
        self.assertEqual(
            case.unknown_fields(), ["etiology", "residual_limb.wound_status", "activity.k_level"]
        )

    def test_not_applicable_unknown_skipped(self):
        case = Case(amputation_level="transradial", side="left",
                    activity=ActivityProfile(k_level="unknown"))
        self.assertEqual(case.unknown_fields(), [])

    def test_empty_is_not_unknown(self):
        self.assertEqual(make_case().unknown_fields(), [])


if __name__ == "__main__":
    unittest.main()
