"""What each Case field means for the knowledge and reasoning layers.

For every intake field that can be an information gap, this says:
- `label`: the name the reviewer sees,
- `query`: what retrieval searches the source library for when the field
  is missing (English; the multilingual model also finds Arabic and German
  passages),
- `topic_terms`: words, per language, that a passage must contain to be
  cited for this field. A passage can score as "similar" without being
  about the field; this check stops a gap from citing an off-topic source.

Order matters: gaps are shown to the reviewer in this order.
Free-text note fields (`residual_limb.notes`, `intake_notes`) are not
listed, so an empty note is never reported as a gap.
"""

import re
from dataclasses import dataclass
from typing import Optional

from shared.case_schema import Case

NOT_RECORDED = "not recorded"
RECORDED_UNKNOWN = "recorded as unknown"

# Arabic short vowels, shadda, sukun and tatweel. Removed before matching
# topic terms, so "الجِلد" matches the term "الجلد".
_ARABIC_MARKS = re.compile("[ـً-ْٰ]")


@dataclass(frozen=True)
class FieldInfo:
    path: str  # dotted Case field path, as in Case.unrecorded_fields()
    label: str
    query: str
    topic_terms: dict[str, str]  # language code -> regular expression

    def topic_span(self, text: str, language: str) -> Optional[tuple[int, int]]:
        """(start, end) of the first topic term in `text`, or None."""
        pattern = self.topic_terms.get(language)
        if pattern is None:
            return None
        # Match on the text without Arabic vowel marks, but report positions
        # in the original text: kept[i] is where stripped character i came from.
        kept = [i for i, char in enumerate(text) if not _ARABIC_MARKS.match(char)]
        match = re.search(pattern, "".join(text[i] for i in kept), re.IGNORECASE)
        if match is None:
            return None
        return kept[match.start()], kept[match.end() - 1] + 1

    def mentions_topic(self, text: str, language: str) -> bool:
        return self.topic_span(text, language) is not None


@dataclass(frozen=True)
class MissingField:
    info: FieldInfo
    status: str  # NOT_RECORDED or RECORDED_UNKNOWN


FIELDS: tuple[FieldInfo, ...] = (
    FieldInfo(
        "residual_limb.wound_status",
        "Residual limb wound status",
        "residual limb wound healing before prosthetic fitting",
        {
            "en": r"\bwound|incision|\bheal(ed|ing)?\b|sutur|dehiscen",
            "de": r"Wund|Naht|Heilung|Narbe",
            "ar": r"جرح|جروح|التئام|يلتئم|ندب",
        },
    ),
    FieldInfo(
        "residual_limb.volume_stability",
        "Residual limb volume stability",
        "residual limb volume fluctuation, edema and shrinkage before socket fitting",
        {
            "en": r"volume|o?edema|swelling|shrink",
            "de": r"Volumen|Ödem|Oedem|Schwellung|Kompression|Schrumpf",
            "ar": r"حجم|وذمة|الوذمة|تورم|انتفاخ",
        },
    ),
    FieldInfo(
        "residual_limb.skin_condition",
        "Residual limb skin condition",
        "residual limb skin condition, scars and skin problems in prosthesis users",
        {
            "en": r"\bskin\b|scar|dermat|ulcer|blister|abrasion",
            "de": r"Haut|Narbe|Druckstelle|Ulkus",
            "ar": r"الجلد|جلد|تقرح|قرحة|ندب",
        },
    ),
    FieldInfo(
        "residual_limb.length_description",
        "Residual limb length and shape",
        "residual limb length and shape assessment",
        {
            "en": r"\blength\b|bony prominen|limb shape|(long|short) residual limb",
            "de": r"Länge|Stumpfform",
            "ar": r"طول|قصير|\bشكل\b",  # \b: not the شكل inside مشكلة ("problem")
        },
    ),
    FieldInfo(
        "residual_limb.pain",
        "Residual limb and phantom pain",
        "residual limb pain and phantom limb pain assessment",
        {
            "en": r"\bpain\b|phantom",
            "de": r"Schmerz|Phantom",
            "ar": r"ألم|آلام|شبح|وهمي",  # not "الم": it starts المعايير ("the standards")
        },
    ),
    FieldInfo(
        "residual_limb.sensation",
        "Residual limb sensation",
        "residual limb sensation, sensory loss and neuropathy",
        {
            # not "phantom (limb) sensation": that's a different finding
            "en": r"(?<!phantom )(?<!phantom limb )sensation|sensory|neuropath|numb|propriocept",
            "de": r"Sensibilität|Empfindung|Gefühl|Neuropath|Taubheit",
            "ar": r"إحساس|\bالحس\b|حسي\b|خدر|تنميل|اعتلال الأعصاب",  # \b: not الحساب
        },
    ),
    FieldInfo(
        "activity.k_level",
        "Functional level (K-level)",
        "functional level K0 K1 K2 K3 K4 classification of prosthetic potential",
        {
            "en": r"\bK-?level|\bK[0-4]\b|functional level|MFCL|functional classification|prosthetic potential",
            "de": r"Mobilitätsgrad|Mobilitätsklasse|Aktivitätsgrad|K-?Level|Funktionsniveau",
            "ar": r"المستوى الوظيفي|مستوى النشاط|القدرة الوظيفية|القدرة على المشي|مستوى التنقل",
        },
    ),
    FieldInfo(
        "activity.description",
        "Current activity and mobility",
        "current daily activities and mobility of the person with amputation",
        {
            "en": r"\bactivit|mobility|ambulat|walking|daily living|\bADLs?\b",
            "de": r"Aktivität|Mobilität|Alltag|Gehfähigkeit|Selbstständigkeit|Selbständigkeit",
            "ar": r"النشاط|الأنشطة|التنقل|الحركة|المشي|الحياة اليومية",
        },
    ),
    FieldInfo(
        "activity.functional_goals",
        "Functional goals",
        "patient goals and expectations for prosthetic rehabilitation",
        {
            # not "expectation": it also matches "manage expectations regarding pain"
            "en": r"\bgoals?\b|patient priorit|participation",
            "de": r"Ziel|Wünsche|Teilhabe",
            "ar": r"أهداف|هدف|الأهداف|المشاركة",
        },
    ),
    FieldInfo(
        "prior_devices",
        "Prior prosthesis use",
        "previous prosthesis use and prosthetic history",
        {
            # not "prosthetic use" alone: it also means use of the new prosthesis
            "en": r"(previous|prior|existing|former|first) prosthe|prosthetic history"
            r"|experienced (prosthesis )?user|new (prosthesis )?user|abandon",
            # not "Prothesenversorgung" (prosthetic fitting in general)
            "de": r"bisherige Prothese|Vorversorgung|Prothesenerfahrung|frühere Prothese"
            r"|Prothesenablehnung",
            "ar": r"البدلة السابقة|البدلات السابقة|الطرف الاصطناعي السابق|الجهاز السابق"
            r"|استخدام البدلة|استخدام البدلات|استخدام الطرف",
        },
    ),
    FieldInfo(
        "comorbidities",
        "Comorbidities",
        "comorbidities such as diabetes and cardiovascular disease in prosthetic rehabilitation",
        {
            "en": r"comorbid|co-morbid|diabet|cardiac|cardiovascular|\bheart\b|kidney|renal"
            r"|pulmonary|medical condition",
            "de": r"Begleiterkrank|Komorbid|Nebendiagnos|Diabet|Herz|Niere|Vorerkrank",
            "ar": r"الأمراض المصاحبة|أمراض مصاحبة|المراضة|السكري|القلب|الكلى|الأمراض المزمنة",
        },
    ),
    FieldInfo(
        "contralateral_limb_status",
        "Contralateral limb status",
        "condition of the contralateral intact limb in lower limb amputation",
        {
            "en": r"contralateral|intact limb|sound limb|remaining limb|other limb|other leg"
            r"|sound side|intact side",
            "de": r"Gegenseite|kontralateral|erhaltene|gesunde Seite|andere Seite|Gegenbein",
            "ar": r"الطرف الآخر|الطرف السليم|الجانب الآخر|الجهة المقابلة",
        },
    ),
    FieldInfo(
        "cognitive_status",
        "Cognitive status",
        "cognitive function and ability to learn prosthesis use, donning and doffing",
        {
            # not "learn" alone: it appears in all kinds of training text
            "en": r"cogniti|memory|dementia|mental status",
            "de": r"Kognit|Gedächtnis|Demenz|Lernfähigkeit|Merkfähigkeit",
            "ar": r"الإدراك|إدراكي|المعرفي|المعرفية|الذاكرة|الخرف",
        },
    ),
    FieldInfo(
        "etiology",
        "Cause of amputation",
        "cause of amputation such as vascular disease, diabetes, trauma or cancer",
        {
            "en": r"etiolog|aetiolog|cause of (the )?amputation|dysvascular|vascular|diabet"
            r"|traum|cancer|tumou?r|infection|congenital",
            "de": r"Ursache|Ätiologie|Trauma|Unfall|Tumor|Gefäß|Diabet|Infektion|angeboren",
            "ar": r"سبب البتر|أسباب البتر|السكري|الصدمة|إصابة|الأورام|السرطان|الأوعية الدموية|عدوى",
        },
    ),
    FieldInfo(
        "months_since_amputation",
        "Time since amputation",
        "time since amputation and timing of prosthetic fitting",
        {
            "en": r"time since|(weeks?|months?) (after|post|following)|post-?operative"
            r"|early (prosthetic )?fitting|pre-?prosthetic|interim|timing",
            "de": r"Zeitpunkt|nach der Amputation|postoperativ|Interimsprothese|Frühversorgung",
            "ar": r"بعد البتر|توقيت|مبكر|المؤقت|المؤقتة",
        },
    ),
    FieldInfo(
        "age_years",
        "Age",
        "patient age in prosthetic rehabilitation assessment",
        {
            "en": r"\bage\b|\baged\b|older adult|elderly|years old",
            "de": r"\bAlter\b|ältere|Lebensalter|Jahre alt",
            "ar": r"العمر|عمر|\bالسن\b|كبار السن|المسنين",  # \b: not السنوات ("years")
        },
    ),
    FieldInfo(
        "body_weight_kg",
        "Body weight",
        "body weight and weight change in prosthetic prescription and socket fit",
        {
            # not "weight" alone: it also matches "weight-bearing"
            "en": r"body ?weight|weight (gain|loss|change|fluctuat)|\bBMI\b|body mass|obes",
            "de": r"Körpergewicht|Gewichts(zunahme|abnahme|schwankung)|\bBMI\b|Adipositas|Übergewicht",
            "ar": r"وزن الجسم|زيادة الوزن|فقدان الوزن|السمنة|البدانة|كتلة الجسم",
        },
    ),
)

FIELDS_BY_PATH = {info.path: info for info in FIELDS}


def missing_fields(case: Case) -> list[MissingField]:
    """The case's information gaps, in FIELDS order: empty or 'unknown' fields."""
    unrecorded = set(case.unrecorded_fields())
    unknown = set(case.unknown_fields())
    missing = []
    for info in FIELDS:
        if info.path in unrecorded:
            missing.append(MissingField(info, NOT_RECORDED))
        elif info.path in unknown:
            missing.append(MissingField(info, RECORDED_UNKNOWN))
    return missing


def build_query(case: Case, info: FieldInfo) -> str:
    """The search text for one missing field, with the case's amputation level."""
    limb = "lower limb" if case.is_lower_limb else "upper limb"
    level = case.amputation_level.value.replace("_", " ")
    return f"{info.query} ({level} amputation, {limb})"
