"""Tests for shared/i18n.py: every interface text exists in every language."""

import re
import unittest

from knowledge.catalog import load_catalog
from review.decision_log import DECISIONS
from shared import case_schema
from shared.config import PROJECT_ROOT
from shared.field_guide import FIELDS, NOT_RECORDED, RECORDED_UNKNOWN
from shared.i18n import (
    FIELD_LABELS,
    LANGUAGES,
    TEXT,
    VALUE_LABELS,
    TranslatableError,
    error_message,
    field_label,
    language_from_cookies,
    placeholders,
    t,
    value_label,
)

ENUMS = [
    case_schema.AmputationLevel,
    case_schema.Side,
    case_schema.Etiology,
    case_schema.ActivityLevel,
    case_schema.WoundStatus,
    case_schema.VolumeStability,
]
OTHER_LANGUAGES = [lang for lang in LANGUAGES if lang != "en"]

# Literal keys in the templates and code: t('intake.heading'),
# TranslatableError("error.yes_no", ...), InvalidDecision("error.edit_needs_note")
_KEY_IN_SOURCE = re.compile(
    r"""(?:\bt|TranslatableError|InvalidDecision)\(\s*['"]([a-z_]+\.[a-z_. ]+)['"]"""
)


class CompletenessTests(unittest.TestCase):
    def test_every_text_in_every_language(self):
        for key, texts in TEXT.items():
            for lang in LANGUAGES:
                with self.subTest(key=key, lang=lang):
                    self.assertTrue(texts.get(lang, "").strip())

    def test_translations_use_only_the_english_placeholders(self):
        # The code passes the English text's placeholders, so a translation
        # may leave one out but never need another.
        for key, texts in TEXT.items():
            for lang in OTHER_LANGUAGES:
                with self.subTest(key=key, lang=lang):
                    self.assertLessEqual(placeholders(texts[lang]), placeholders(texts["en"]))

    def test_every_text_can_be_filled_in(self):
        for key, texts in TEXT.items():
            values = {name: "x" for name in placeholders(texts["en"])}
            for lang in LANGUAGES:
                with self.subTest(key=key, lang=lang):
                    t(key, lang, **values)  # a broken {placeholder} raises

    def test_every_gap_field_has_a_label(self):
        for lang in OTHER_LANGUAGES:
            with self.subTest(lang=lang):
                self.assertEqual(set(FIELD_LABELS[lang]), {info.path for info in FIELDS})

    def test_every_choice_has_a_label(self):
        for lang in OTHER_LANGUAGES:
            for enum in ENUMS:
                with self.subTest(lang=lang, enum=enum.__name__):
                    self.assertEqual(set(VALUE_LABELS[lang][enum.__name__]), {m.value for m in enum})

    def test_keys_used_in_templates_and_code_exist(self):
        files = [*PROJECT_ROOT.glob("*/templates/*.html"), *PROJECT_ROOT.glob("*/*.py")]
        used = {key for path in files for key in _KEY_IN_SOURCE.findall(path.read_text(encoding="utf-8"))}
        self.assertGreater(len(used), 50)  # the pattern still finds them
        self.assertEqual(used - set(TEXT), set())

    def test_keys_built_from_values_exist(self):
        # Templates build these keys: 'status.' ~ gap.status, 'decision.' ~ ...
        expected = {f"status.{status}" for status in (NOT_RECORDED, RECORDED_UNKNOWN)}
        expected |= {f"decision.{decision}" for decision in DECISIONS}
        expected |= {f"doclang.{doc.language}" for doc in load_catalog()}
        expected |= {"error.required.amputation_level", "error.required.side"}  # intake _required()
        self.assertEqual(expected - set(TEXT), set())


class TextTests(unittest.TestCase):
    def test_english_unchanged_arabic_isolated(self):
        self.assertEqual(t("intake.device", "en", n=2), "Device 2")
        # Inserted values are wrapped in bidi isolates in right-to-left text.
        self.assertEqual(t("intake.device", "ar", n=2), "الجهاز \u20682\u2069")

    def test_labels(self):
        self.assertEqual(field_label("residual_limb.pain", "en"), "Residual limb and phantom pain")
        self.assertEqual(field_label("residual_limb.pain", "ar"), "ألم الطرف المتبقي والألم الشبحي")
        level = case_schema.AmputationLevel.KNEE_DISARTICULATION
        self.assertEqual(value_label(level, "en"), "knee disarticulation")
        self.assertEqual(value_label(level, "ar"), "فصل مفصل الركبة")

    def test_language_from_cookies(self):
        self.assertEqual(language_from_cookies({}), "en")
        self.assertEqual(language_from_cookies({"lang": "ar"}), "ar")
        self.assertEqual(language_from_cookies({"lang": "fr"}), "en")

    def test_gap_explanations_never_recommend(self):
        for key in ("gap.not_recorded", "gap.recorded_unknown", "gap.no_source", "gap.cited"):
            with self.subTest(key=key):
                self.assertNotIn("recommend", TEXT[key]["en"].lower())
                self.assertIsNone(re.search(r"توص|يوصى|نوصي|ننصح|يُنصح", TEXT[key]["ar"]))


class ErrorTests(unittest.TestCase):
    def test_str_is_english(self):
        error = TranslatableError("error.device_details_only", n=2)
        self.assertEqual(str(error), "prior device 2: describe the device, not only its details")
        self.assertIsInstance(error, ValueError)

    def test_message_in_arabic_with_wrapped_error_translated(self):
        error = TranslatableError("error.device_invalid", n=1,
                                  detail=TranslatableError("error.yes_no", value="maybe"))
        self.assertEqual(str(error), "prior device 1: expected yes or no, got 'maybe'")
        plain = re.sub("[\u2068\u2069]", "", error.message("ar"))
        self.assertEqual(plain, "الجهاز السابق 1: القيمة المتوقعة «نعم» أو «لا»، والمُرسَلة «maybe»")

    def test_other_errors_shown_as_they_are(self):
        self.assertEqual(error_message(ValueError("could not convert"), "ar"), "could not convert")


if __name__ == "__main__":
    unittest.main()
