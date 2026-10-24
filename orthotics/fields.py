"""The orthotics field guide (use case 03, stroke AFO; added 2026-10-22).

The mechanics (FieldInfo, missing_fields, ...) are in shared/field_guide.py.
"""

from orthotics.case import OrthoticCase
from shared.field_guide import FieldInfo

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

FIELDS: tuple[FieldInfo, ...] = (
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

FIELDS_BY_PATH = {info.path: info for info in FIELDS}


def query_for(case: OrthoticCase, info: FieldInfo) -> str:
    """The search text for one missing field: the field's query as written.

    It already names stroke where that matters. Adding the case's side and months since onset
    cost 6 of 26 right passages (knowledge/evaluate.py --orthotics, 2026-10-22), since the only
    orthotic condition so far is stroke.
    """
    return info.query
