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
# A whole key, never a prefix a key is built from at runtime ('fu.back_to.' ~ b ends with its dot:
# the keys it builds are in test_keys_built_from_values_exist).
_KEY_IN_SOURCE = re.compile(
    r"""(?:\bt|TranslatableError|InvalidDecision)\(\s*['"]([a-z_]+\.[a-z_. ]*[a-z_])['"]"""
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
        from orthotics.plan import BACK_TO
        from shared.followup import VisitStatus
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
        from prosthetics import modules as prosthetic_modules
        for prefix in ("pmod", "pmap_name", "pmap_does"):
            expected |= {f"{prefix}.{key}" for key in prosthetic_modules.MODULES}
        # Every domain's hard stops, alert targets and the words it gives the shared pieces (nav.py WORDS)
        from shared import domains
        for domain in domains.DOMAINS:
            rules = domains.part(domain, "hard_stops")
            expected |= {f"{prefix}.{rule}" for prefix in ("hard", "hard_rule") for rule in rules.RULES}
            expected |= {f"hard_detail.{detail}" for detail in rules.DETAILS}
            expected |= {f"fu.back_to.{key}" for key in domains.part(domain, "plan").BACK_TO}
            nav = domains.part(domain, "nav")
            expected |= set(nav.WORDS.values()) | {nav.REVIEW_BACK[1], nav.REVIEW_NEXT[1], nav.DECIDES}
        # The prosthetic module pages (plan Part 3, 2026-10-24): steps, short names, finding groups, form labels
        from prosthetics import plan as prosthetic_plan
        expected |= {f"pstep.{step.value}" for step in prosthetic_plan.FittingStep}
        expected |= {"prow." + path.replace(".", "__") for path in prosthetic_modules.SHORT_NAMES}
        expected |= {f"req_group.{group}" for group in prosthetic_plan.FINDING_GROUPS}
        expected |= {f"passess.{name}" for name in prosthetic_modules.TEXT_VALUES}  # form labels (a refusal names them)
        expected |= {f"pcomp.{key}" for key in ("funding", "stock", "notes", "costs", "checks")}
        # The reasoning and review part's pages (plan Part 4, 2026-10-25): its name and tabs, the pathway's steps,
        # the quality page's run modes and audit lines, the review page's decisions and its new mark
        from quality import results
        expected |= {f"part.{name}" for name in domains.SHARED_PARTS}
        for name in domains.SHARED_PARTS:  # each shared part's tabs (review: Part 4, knowledge: Part 5)
            nav = domains.nav(name)
            expected |= {nav.LABELS + key for key, _, _ in nav.MODULES}
        steps = ("case_data", "analysis", "reasoning", "output", "review", "outcome")
        expected |= {f"{prefix}.{key}" for prefix in ("path_step", "path_does", "path_guard") for key in steps}
        expected |= {f"path_never.{key}" for key in ("diagnosis", "prescription", "ranking", "readiness", "unquoted")}
        expected |= {f"path_sends.{domain}" for domain in domains.DOMAINS}
        expected |= {f"run_mode.{mode}" for mode in (results.NO_SEARCH, results.SEARCH, results.RAG)}
        expected |= {f"audit.{what}" for what in ("decision", "design_choice", "release_check", "release_check_failed",
                                                   "library", "rule_approved", "arabic_checked", "signed_off")}
        expected |= {f"audit.golden_{name}" for name in (results.DEVELOPMENT, results.HELD_OUT)}
        expected |= {f"review.{decision}" for decision in DECISIONS} | {"summary.summary_wrong"}
        # The knowledge layer's pages (plan Part 5, 2026-10-25): statuses, steps, reasons, curator lines, domains
        from knowledge import library, routes as knowledge_routes
        from knowledge.catalog import DOMAINS as CATALOG_DOMAINS
        from knowledge.models import VALIDATION_STATUSES
        expected |= {f"kstatus.{status}" for status in library.STATUSES}
        steps = ("licence", "text", "clean", "passages", "index")
        expected |= {f"{prefix}.{step}" for prefix in ("kstep", "kstep_does") for step in steps}
        expected |= {f"kreason.{reason}" for reason in knowledge_routes.REASONS}
        expected |= {f"kvalidation.{status}" for status in VALIDATION_STATUSES}
        expected |= {f"kdomain.{domain}" for domain in CATALOG_DOMAINS}
        expected |= {f"source_type.{kind}" for kind in knowledge_routes.KINDS}
        expected |= {f"curate.{what}" for what in ("not_extracted", "not_in_index", "link_only", "search_quality_due")}
        expected |= {f"{prefix}.{key}" for prefix in ("kgr_part", "kgr_does") for key in ("graph", "cases", "data")}
        expected |= {"kev.other_topic", "functional.heading", "audit.search_quality", "audit.search_quality_orthotics"}
        # Smart search (plan Part 6, 2026-10-25): its languages, marks and the curator's line for suggestions
        from search import engine as search_engine, log as search_log
        expected |= {f"srch_lang.{language}" for language in search_engine.LANGUAGES}
        expected |= {f"srch_mark.{mark}" for mark in search_log.MARKS} | {"curate.suggested"}
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
