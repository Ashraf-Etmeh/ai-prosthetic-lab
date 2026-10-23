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
    # Orthotics only, a PROPOSAL awaiting the owner (2026-10-22): information the
    # orthotist needs before weighing an orthosis. The page marks such a gap; it
    # hides nothing. Prosthetic fields are never marked.
    critical: bool = False

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

# ---- Orthotics (use case 03, stroke AFO; added 2026-10-22) -------------------
#
# PROPOSAL, awaiting the owner's and an orthotist's review: the fields, their
# order and which are `critical` follow the stroke-AFO proposal of 2026-10-21
# (blueprint section 7 plus the discussion). Paths are OrthoticCase paths; the
# core fields (age, body weight, comorbidities, cognition) share their path and
# label with the prosthetic ones but search with orthotic wording.
# Not listed (never a gap): walking aid, the gait-speed test and tone scale
# (checked together with their value), free-text notes, the implanted
# electronic device (asked only if FES is discussed) and the orthotist's own
# requirements.

# "numb" as a word only ("absolute numbers" is not numbness); "protective" only with sensation.
_EN_SENSATION = r"(?<!phantom )sensation|sensory|neuropath|\bnumb(ness)?\b|protective (sensation|feeling)|monofilament"
_AR_SENSATION = r"إحساس|\bالحس\b|حسي\b|خدر|تنميل|اعتلال الأعصاب"
_EN_ROM = r"dorsiflex|range of (motion|movement)|\bROM\b|gastrocnemius|soleus|calf (muscle )?length|contracture"
_DE_ROM = r"Dorsalextension|Bewegungsumfang|Beweglichkeit|Kontraktur|Wadenmuskulatur|Soleus"
_AR_ROM = r"مدى الحركة|العطف الظهري|ثني الكاحل|تيبس|تقفع|انكماش"

ORTHOTIC_FIELDS: tuple[FieldInfo, ...] = (
    FieldInfo(
        "months_since_onset",
        "Time since stroke",
        "time since stroke onset: acute or chronic phase and timing of ankle-foot orthosis provision",
        {
            "en": r"\bacute\b|\bchronic\b|sub-?acute|(weeks?|months?) (after|post|following)|time since|onset|timing",
            "de": r"akut|chronisch|subakut|Monate nach|Wochen nach|Zeitpunkt|Frühphase",
            "ar": r"حاد|الحادة|مزمن|المزمنة|بعد السكتة|توقيت|المرحلة",
        },
        critical=True,
    ),
    FieldInfo(
        "functional_goals",
        "Functional goals",
        "patient goals for using an ankle-foot orthosis after stroke: walking, mobility, participation",
        {
            "en": r"\bgoals?\b|patient priorit|participation",
            "de": r"Ziel|Wünsche|Teilhabe",
            "ar": r"أهداف|هدف|الأهداف|المشاركة",
        },
        critical=True,
    ),
    FieldInfo(
        "exam.dorsiflexion_knee_extended_deg",
        "Ankle dorsiflexion, knee extended",
        "passive ankle dorsiflexion range with the knee extended (gastrocnemius length) before an ankle-foot orthosis",
        {"en": _EN_ROM, "de": _DE_ROM, "ar": _AR_ROM},
        critical=True,
    ),
    FieldInfo(
        "exam.dorsiflexion_knee_flexed_deg",
        "Ankle dorsiflexion, knee flexed",
        "passive ankle dorsiflexion range with the knee flexed (soleus length) before an ankle-foot orthosis",
        {"en": _EN_ROM, "de": _DE_ROM, "ar": _AR_ROM},
        critical=True,
    ),
    FieldInfo(
        "exam.protective_sensation",
        "Protective sensation of the foot",
        "foot sensation and loss of protective sensation: pressure and skin risk with an ankle-foot orthosis",
        {
            "en": _EN_SENSATION,
            "de": r"Sensibilität|Empfindung|Gefühl|Neuropath|Taubheit",
            "ar": _AR_SENSATION,
        },
        critical=True,
    ),
    FieldInfo(
        "exam.skin_condition",
        "Skin of the foot and leg",
        "skin integrity, pressure areas and skin checks when wearing an ankle-foot orthosis",
        {
            "en": r"\bskin\b(?![- ]surface)|pressure (area|sore|ulcer|point)|redness|ulcer|blister",  # not "skin surface FES"
            "de": r"Haut|Druckstelle|Rötung|Ulkus|Blase",
            "ar": r"\bالجلد\b|\bجلد\b|احمرار|تقرح|قرحة|بثور",
        },
        critical=True,
    ),
    FieldInfo(
        "walking.status",
        "Walking status",
        "walking ability after stroke: independent, with a walking aid or with assistance",
        {
            "en": r"ambulat|walking (ability|status)|walk(s|ed)? independently|walking aid|\bcane\b|walker"
            r"|Functional Ambulation",
            "de": r"Gehfähigkeit|gehfähig|Gehhilfe|Rollator|Gehstock",
            "ar": r"المشي|التنقل|عكاز|مشاية|العصا",
        },
    ),
    FieldInfo(
        "walking.gait_speed_m_s",
        "Gait speed (with the test named)",
        "gait speed after stroke measured with a timed walk test such as the 10-metre walk test",
        {
            "en": r"gait speed|walking speed|10[- ]?m(eter|etre)? walk|10MWT|\bm/s\b",
            "de": r"Gehgeschwindigkeit|10-Meter|\bm/s\b",
            "ar": r"سرعة المشي|م/ث",
        },
    ),
    FieldInfo(
        "exam.plantarflexor_tone_grade",
        "Plantarflexor tone (scale and grade)",
        "plantarflexor muscle tone and spasticity after stroke: assessment with the Modified Ashworth or Tardieu scale",
        {
            "en": r"spastic|Ashworth|Tardieu|\btone\b|hypertoni",
            "de": r"Spastik|spastisch|Ashworth|Tardieu|Tonus",
            "ar": r"تشنج|التشنج|الشد العضلي|التوتر العضلي|آشورث",
        },
    ),
    FieldInfo(
        "exam.dorsiflexor_strength",
        "Dorsiflexor strength",
        "ankle dorsiflexor weakness and foot drop after stroke",
        {
            "en": r"dorsiflexor|tibialis anterior|foot drop|drop foot|weakness|muscle strength|\bMRC\b",
            "de": r"Fußheber|Fallfuß|Fußheberschwäche|Parese|Kraft",
            "ar": r"ضعف|قوة العضلات|القدم المتدلية|هبوط القدم|تدلي القدم",
        },
    ),
    FieldInfo(
        "exam.knee_extensor_strength",
        "Knee extensor strength",
        "knee extensor strength and knee control in stance with an ankle-foot orthosis",
        {
            "en": r"quadriceps|knee extensor|knee control|muscle strength|weakness",
            "de": r"Quadrizeps|Kniestrecker|Kniekontrolle|Kraft",
            "ar": r"العضلة الرباعية|باسطات الركبة|التحكم في الركبة|قوة|ضعف",
        },
    ),
    FieldInfo(
        "exam.knee_in_stance",
        "Knee in stance (hyperextension or buckling)",
        "knee hyperextension (genu recurvatum) or knee buckling in stance after stroke and ankle-foot orthoses",
        {
            "en": r"hyperextens|recurvatum|buckl|knee (flexion|extension|control|instability)",
            "de": r"Hyperextension|Überstreckung|Rekurvation|recurvatum|Knieinstabilität",
            "ar": r"فرط بسط الركبة|فرط تمدد الركبة|انثناء الركبة|الركبة",
        },
    ),
    FieldInfo(
        "walking.deviations",
        "Gait deviations by phase",
        "observational gait analysis after stroke: foot drop in swing, knee hyperextension in stance, compensations",
        {
            "en": r"gait (deviation|pattern|analysis)|swing phase|stance phase|toe drag|foot drop|circumduction"
            r"|hip hitching",
            "de": r"Gangbild|Gangabweichung|Schwungphase|Standphase|Ganganalyse|Zirkumduktion",
            "ar": r"نمط المشي|المشية|مرحلة الأرجحة|مرحلة الارتكاز|تحليل المشي",
        },
    ),
    FieldInfo(
        "walking.falls_last_6_months",
        "Falls",
        "falls and fall risk after stroke, with and without an ankle-foot orthosis",
        {
            "en": r"\bfalls?\b|fall risk|falling",
            "de": r"Sturz|Stürze|Sturzrisiko",
            "ar": r"السقوط|سقوط|الوقوع",
        },
    ),
    FieldInfo(
        "exam.foot_posture",
        "Foot posture (flexible or rigid)",
        "foot deformity after stroke such as equinovarus, flexible or fixed, and orthosis design",
        {
            "en": r"equinus|equinovarus|varus|valgus|deformit|flexible|rigid|fixed",
            "de": r"Spitzfuß|Klumpfuß|Fehlstellung|Deformität|kontrakt|flexibel",
            "ar": r"تشوه|القدم القفداء|القدم الروحاء|انحراف القدم",
        },
    ),
    FieldInfo(
        "exam.proprioception",
        "Proprioception",
        "loss of proprioception (joint position sense) after stroke and balance",
        {
            "en": r"propriocept|position sense|joint position",
            "de": r"Propriozeption|Lagesinn|Tiefensensibilität",
            "ar": r"الحس العميق|حس الوضع|استقبال الحس العميق",
        },
    ),
    FieldInfo(
        "footwear",
        "Footwear",
        "footwear worn with an ankle-foot orthosis: shoe fit and heel height",
        {
            "en": r"footwear|\bshoes?\b|heel (height|pitch|wedge|raise)",
            "de": r"Schuh|Schuhwerk|Absatz|Fersenkeil",
            "ar": r"الحذاء|أحذية|حذاء|كعب",
        },
    ),
    FieldInfo(
        "donning",
        "Putting the orthosis on",
        "donning and doffing an ankle-foot orthosis, with one hand after stroke",
        {
            "en": r"\bdon(s|ning)?\b|doff|put(ting)? (it |the orthosis )?on|one[- ]hand",
            "de": r"Anlegen|Anziehen|einhändig|Ablegen",
            "ar": r"ارتداء|لبس|نزع|بيد واحدة",
        },
    ),
    FieldInfo(
        "prior_orthoses",
        "Previous orthoses or FES",
        "previous use of ankle-foot orthoses or functional electrical stimulation, and wearing them",
        {
            "en": r"(previous|prior|existing|current|first) (orthos|AFO|brace|device)|adherence|compliance"
            r"|abandon|wearing time",
            "de": r"bisherige Orthese|Vorversorgung|Tragedauer|Akzeptanz|Tragezeit",
            "ar": r"الجهاز السابق|الالتزام|مدة الارتداء|التخلي عن",
        },
    ),
    FieldInfo(
        "comorbidities",
        "Comorbidities",
        "comorbidities after stroke such as diabetes and heart disease that bear on orthosis use",
        {
            "en": r"comorbid|co-morbid|diabet|cardiac|cardiovascular|\bheart\b|kidney|renal|medical condition",
            "de": r"Begleiterkrank|Komorbid|Nebendiagnos|Diabet|Herz|Niere|Vorerkrank",
            "ar": r"الأمراض المصاحبة|أمراض مصاحبة|المراضة|السكري|القلب|الكلى|الأمراض المزمنة",
        },
    ),
    FieldInfo(
        "cognitive_status",
        "Cognitive status",
        "cognition and the ability to learn to use and look after an orthosis after stroke",
        {
            "en": r"cogniti|memory|dementia|mental status",
            "de": r"Kognit|Gedächtnis|Demenz|Lernfähigkeit|Merkfähigkeit",
            "ar": r"الإدراك|إدراكي|المعرفي|المعرفية|الذاكرة|الخرف",
        },
    ),
    FieldInfo(
        "age_years",
        "Age",
        "patient age in rehabilitation and orthosis provision after stroke",
        {
            "en": r"\bage\b|\baged\b|older adult|elderly|years old",
            "de": r"\bAlter\b|ältere|Lebensalter|Jahre alt",
            "ar": r"العمر|عمر|\bالسن\b|كبار السن|المسنين",
        },
    ),
    FieldInfo(
        "body_weight_kg",
        "Body weight",
        "body weight and the design and material thickness of an ankle-foot orthosis",
        {
            "en": r"body ?weight|weight (gain|loss|change)|\bBMI\b|body mass|obes|patient'?s weight",
            "de": r"Körpergewicht|Gewicht des Patienten|\bBMI\b|Adipositas|Übergewicht",
            "ar": r"وزن الجسم|وزن المريض|السمنة|البدانة|كتلة الجسم",
        },
    ),
)

# Labels by path for both domains. A core path (age, comorbidities, ...) is
# in both lists with the same label, so either entry names it.
FIELDS_BY_PATH = {info.path: info for info in FIELDS}
for _info in ORTHOTIC_FIELDS:
    FIELDS_BY_PATH.setdefault(_info.path, _info)
ORTHOTIC_FIELDS_BY_PATH = {info.path: info for info in ORTHOTIC_FIELDS}


def fields_for(case) -> tuple[FieldInfo, ...]:
    """The gap fields of the case's domain."""
    return ORTHOTIC_FIELDS if case.domain == "orthotics" else FIELDS


def missing_fields(case: Case) -> list[MissingField]:
    """The case's information gaps, in its field guide's order: empty or 'unknown' fields."""
    unrecorded = set(case.unrecorded_fields())
    unknown = set(case.unknown_fields())
    missing = []
    for info in fields_for(case):
        if info.path in unrecorded:
            missing.append(MissingField(info, NOT_RECORDED))
        elif info.path in unknown:
            missing.append(MissingField(info, RECORDED_UNKNOWN))
    return missing


def build_query(case: Case, info: FieldInfo) -> str:
    """The search text for one missing field, with the case's amputation level.

    An orthotic field's query is searched as written: it already names stroke
    where that matters. Adding the case's side and months since onset cost
    6 of 26 right passages (knowledge/evaluate.py --orthotics, 2026-10-22),
    since the only orthotic condition so far is stroke.
    """
    if case.domain == "orthotics":
        return info.query
    limb = "lower limb" if case.is_lower_limb else "upper limb"
    level = case.amputation_level.value.replace("_", " ")
    return f"{info.query} ({level} amputation, {limb})"
