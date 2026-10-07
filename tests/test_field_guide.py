"""Tests for shared/field_guide.py: field coverage, queries and topic terms."""

import re
import unittest

from shared.case_schema import ActivityProfile, Case
from shared.field_guide import (
    FIELDS,
    FIELDS_BY_PATH,
    NOT_RECORDED,
    RECORDED_UNKNOWN,
    build_query,
    missing_fields,
)

NOTES = {"intake_notes", "residual_limb.notes"}


class CoverageTests(unittest.TestCase):
    def test_every_guide_path_is_a_case_field(self):
        paths = {path for path, _ in Case(amputation_level="syme", side="left")._leaf_values()}
        for info in FIELDS:
            self.assertIn(info.path, paths)

    def test_every_unrecorded_field_except_notes_is_in_the_guide(self):
        blank = Case(amputation_level="transfemoral", side="left")
        self.assertEqual(set(blank.unrecorded_fields()) - NOTES, set(FIELDS_BY_PATH))

    def test_topic_terms_for_all_three_languages_compile(self):
        for info in FIELDS:
            self.assertEqual(set(info.topic_terms), {"en", "de", "ar"}, info.path)
            for pattern in info.topic_terms.values():
                re.compile(pattern)


class TopicTermTests(unittest.TestCase):
    def test_matches_in_each_language(self):
        pain = FIELDS_BY_PATH["residual_limb.pain"]
        self.assertTrue(pain.mentions_topic("Phantom limb pain is common.", "en"))
        self.assertTrue(pain.mentions_topic("Phantomschmerzen treten häufig auf.", "de"))
        self.assertTrue(pain.mentions_topic("ألم الطرف الشبحي شائع.", "ar"))

    def test_arabic_look_alike_words_do_not_match(self):
        # "the standards", "problem", "the years" contain the letters of pain/shape/age words.
        self.assertFalse(FIELDS_BY_PATH["residual_limb.pain"].mentions_topic("المعايير", "ar"))
        self.assertFalse(FIELDS_BY_PATH["residual_limb.length_description"].mentions_topic("مشكلة", "ar"))
        self.assertFalse(FIELDS_BY_PATH["age_years"].mentions_topic("السنوات", "ar"))

    def test_near_misses_found_in_real_documents_do_not_match(self):
        cases = [
            ("body_weight_kg", "lower limb devices are critical for weight-bearing function"),
            ("residual_limb.sensation", "PLP Phantom sensations 4.94 (P<0.05)"),
            ("residual_limb.sensation", "Assess phantom limb sensation (PLS)."),
            ("activity.functional_goals", "Manage expectations regarding pain post-amputation."),
            ("cognitive_status", "Patients learn to use the terminal device in therapy."),
            ("prior_devices", "improve body contour and possibly prosthetic use"),
        ]
        for path, text in cases:
            with self.subTest(path):
                self.assertFalse(FIELDS_BY_PATH[path].mentions_topic(text, "en"))
        self.assertFalse(FIELDS_BY_PATH["prior_devices"].mentions_topic(
            "Danach ist eine Prothesenversorgung möglich.", "de"))  # fitting in general
        self.assertTrue(FIELDS_BY_PATH["body_weight_kg"].mentions_topic("Body weight changes alter socket fit.", "en"))
        self.assertTrue(FIELDS_BY_PATH["residual_limb.sensation"].mentions_topic("Check residual limb sensation.", "en"))

    def test_unknown_language_never_matches(self):
        self.assertFalse(FIELDS_BY_PATH["residual_limb.pain"].mentions_topic("pain", "fr"))


class MissingFieldTests(unittest.TestCase):
    def test_empty_and_unknown_fields(self):
        case = Case(amputation_level="transtibial", side="left",
                    activity=ActivityProfile(k_level="unknown"))
        status = {m.info.path: m.status for m in missing_fields(case)}
        self.assertEqual(status["activity.k_level"], RECORDED_UNKNOWN)
        self.assertEqual(status["comorbidities"], NOT_RECORDED)

    def test_query_names_the_amputation_level(self):
        case = Case(amputation_level="knee_disarticulation", side="left")
        query = build_query(case, FIELDS_BY_PATH["residual_limb.pain"])
        self.assertIn("knee disarticulation amputation, lower limb", query)
