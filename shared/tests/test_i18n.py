"""Tests for shared/i18n.py: every interface text exists in every language."""

import re
import unittest

from knowledge.catalog import SOURCE_TYPES, load_catalog
from orthotics import case as orthotic_case
from orthotics.fields import FIELDS as ORTHOTIC_FIELDS
from orthotics.topics import DESIGN_SECTIONS, DEVICE_SECTIONS, PARTS as ORTHOTIC_PARTS
from prosthetics import case as prosthetic_case
from prosthetics.component_guide import COMPONENT_KEYS, GRADES
from prosthetics.component_support import NOTE_K0, NOTE_K_NOT_RECORDED
from prosthetics.fields import FIELDS
from prosthetics.fitting_guide import SECTION_KEYS
from prosthetics.topics import PARTS
from reasoning.rag import GRADE_PHRASES
from review.decision_log import DECISIONS
from shared import case_schema
from shared.config import CODE_PACKAGES, PROJECT_ROOT
from shared.field_guide import NOT_RECORDED, RECORDED_UNKNOWN
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
    prosthetic_case.AmputationLevel,
    case_schema.Side,
    prosthetic_case.Etiology,
    prosthetic_case.ActivityLevel,
    prosthetic_case.WoundStatus,
    prosthetic_case.VolumeStability,
    # Orthotics (2026-10-22)
    orthotic_case.OrthoticCondition,
    orthotic_case.WalkingStatus,
    orthotic_case.KneeInStance,
    orthotic_case.SensationStatus,
    orthotic_case.ToneScale,
    orthotic_case.DonningAbility,
    case_schema.YesNoUnknown,
    orthotic_case.GaitDeviation,
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
                self.assertEqual(set(FIELD_LABELS[lang]), {info.path for info in (*FIELDS, *ORTHOTIC_FIELDS)})

    def test_every_choice_has_a_label(self):
        for lang in OTHER_LANGUAGES:
            for enum in ENUMS:
                with self.subTest(lang=lang, enum=enum.__name__):
                    self.assertEqual(set(VALUE_LABELS[lang][enum.__name__]), {m.value for m in enum})

    def test_keys_used_in_templates_and_code_exist(self):
        files = [path for package in (*CODE_PACKAGES, "scripts") for path in (PROJECT_ROOT / package).rglob("*")
                 if path.suffix in (".py", ".html") and "__pycache__" not in path.parts]
        used = {key for path in files for key in _KEY_IN_SOURCE.findall(path.read_text(encoding="utf-8"))}
        self.assertGreater(len(used), 50)  # the pattern still finds them
        self.assertEqual(used - set(TEXT), set())

    def test_keys_built_from_values_exist(self):
        # Templates build these keys: 'status.' ~ gap.status, 'decision.' ~ ...
        expected = {f"status.{status}" for status in (NOT_RECORDED, RECORDED_UNKNOWN)}
        expected |= {f"decision.{decision}" for decision in DECISIONS}
        expected |= {f"doclang.{doc.language}" for doc in load_catalog()}
        expected |= {"error.required.amputation_level", "error.required.side"}  # intake _required()
        # Component sections: 'component.' ~ key, 'grade.' ~ (grade or 'none'), t(note)
        expected |= {f"component.{key}" for key in COMPONENT_KEYS}
        expected |= {f"grade.{grade}" for grade in (*GRADES, "none")}
        expected |= {NOTE_K0, NOTE_K_NOT_RECORDED}
        # Fitting sections and every statement's kind of source
        expected |= {f"fitting_section.{key}" for key in SECTION_KEYS}
        expected |= {f"source_type.{source_type}" for source_type in SOURCE_TYPES}
        expected |= {"summary.components", "summary.fitting"}  # review/routes.py judgement_summary
        # The RAG: 'ai_part.' ~ part.kind for an unavailable part, and any grade a passage may print
        expected |= {f"ai_part.{part}" for part in PARTS}
        expected |= {f"grade.{grade}" for grade in GRADE_PHRASES}
        # Orthotics (2026-10-22): its sections, AI parts, gait phases, its summary heading and required field
        expected |= {f"component.{key}" for key in DEVICE_SECTIONS}
        expected |= {f"fitting_section.{key}" for key in DESIGN_SECTIONS}
        expected |= {f"ai_part.{part}" for part in ORTHOTIC_PARTS}
        expected |= {f"phase.{phase}" for phase in orthotic_case.GAIT_PHASES}
        expected |= {"summary.orthotic_options", "error.required.condition"}
        # Orthotic modules (2026-10-23): the header's modules, the map, and each vocabulary of orthotics/plan.py
        from orthotics import plan
        from review.decision_log import DESIGN_CHOICE
        expected |= {f"mod.{key}" for key in ("analyse", "requirements", "options", "design", "fit", "follow_up")}
        for prefix in ("chain", "chain_module"):
            expected |= {f"{prefix}.{key}" for key in ("impairments", "gait", "requirements", "options", "fabrication",
                                                        "fit", "training", "follow_up")}
        from orthotics import hard_stops, modules
        from orthotics.followup import BACK_TO, VisitStatus
        for prefix in ("map_name", "map_does"):
            expected |= {f"{prefix}.{key}" for key in modules.MODULES}
        expected |= {f"req_group.{group}" for group in ("gait", "exam", "other", "missing")}
        for prefix, vocabulary in (("priority", plan.Priority), ("mark", plan.Mark), ("device", plan.DeviceType),
                                   ("part", plan.Part), ("step", plan.Step), ("step_status", plan.StepStatus),
                                   ("method", plan.Method), ("basis", plan.Basis), ("visit_status", VisitStatus)):
            expected |= {f"{prefix}.{member.value}" for member in vocabulary}
        expected |= {f"param.{key}" for key in plan.PARAMETERS}
        expected |= {f"decision.{DESIGN_CHOICE}"}
        # The design canvas's screens (2026-10-23): conditions, ICF levels, the case's values, the hard stops,
        # the map's knowledge boxes and roll-out, where an alert loops back to.
        expected |= {f"cond.{key}" for key in modules.CONDITIONS}
        expected |= {f"icf.{key}" for key in ("participation", "activity", "body_function")}
        paths = {path for path, _ in modules.EXAM_ROWS} | set(plan.FINDING_PATHS)
        expected |= {"exam_row." + path.replace(".", "__") for path in paths}
        for prefix in ("hard", "hard_rule"):
            expected |= {f"{prefix}.{rule}" for rule in hard_stops.RULES}
        expected |= {f"hard_detail.{detail}" for detail in hard_stops.DETAILS}
        expected |= {f"hard_status.{status}" for status in hard_stops.STATUSES}
        for prefix in ("know", "know_does", "know_here"):
            expected |= {f"{prefix}.{key}" for key in ("guidelines", "manuals", "graph", "cases", "expertise", "data",
                                                        "glossary")}
        expected |= {f"rollout.{key}" for key in ("stroke_afo", "cp_afo", "diabetic_foot", "scoliosis_kafo", "digital")}
        expected |= {f"fu.back_to.{key}" for key in BACK_TO}
        # Every page's header (2026-10-23): 'domain.' ~ domain, the prosthetic modules, the prosthetics map
        expected |= {"domain.prosthetics", "domain.orthotics"}
        for prefix in ("pmod", "pmap_name", "pmap_does"):
            expected |= {f"{prefix}.{key}" for key in ("evaluate", "functional", "components", "fitting")}
        self.assertEqual(expected - set(TEXT), set())


class TextTests(unittest.TestCase):
    def test_english_unchanged_arabic_isolated(self):
        self.assertEqual(t("intake.device", "en", n=2), "Device 2")
        # Inserted values are wrapped in bidi isolates in right-to-left text.
        self.assertEqual(t("intake.device", "ar", n=2), "الجهاز \u20682\u2069")

    def test_labels(self):
        self.assertEqual(field_label("residual_limb.pain", "en"), "Residual limb and phantom pain")
        self.assertEqual(field_label("residual_limb.pain", "ar"), "ألم الطرف المتبقي والألم الشبحي")
        level = prosthetic_case.AmputationLevel.KNEE_DISARTICULATION
        self.assertEqual(value_label(level, "en"), "knee disarticulation")
        self.assertEqual(value_label(level, "ar"), "فصل مفصل الركبة")

    def test_language_from_cookies(self):
        self.assertEqual(language_from_cookies({}), "en")
        self.assertEqual(language_from_cookies({"lang": "ar"}), "ar")
        self.assertEqual(language_from_cookies({"lang": "fr"}), "en")

    def test_gap_explanations_never_recommend(self):
        for key in ("gap.not_recorded", "gap.recorded_unknown", "gap.no_source", "gap.cited",
                    "fitting.intro", "fitting.recorded"):
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
