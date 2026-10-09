"""Interface text in English and Arabic.

The pages show every heading, label, button, message and gap explanation in
the reviewer's chosen language. All of it is in this file, so one file can be
checked by an Arabic-reading specialist. English is the default; a link at
the top of each page switches language, remembered in a cookie.

Not translated:
- quotes and passages from the source library (shown in their own language),
- citations (title, year and page of the source document),
- what the user typed into the form,
- technical messages for whoever runs the app (e.g. "Build it with:
  python -m knowledge.ingest") and Python's own wording for impossible form
  values, which the form's drop-downs and number inputs normally prevent.

The review log stays in English (field labels, gap explanations) and records
the language the reviewer saw as "ui_language", so entries can be compared
whichever language was used.
"""

from string import Formatter

from shared.config import DISCLAIMER
from shared.field_guide import FIELDS_BY_PATH

LANGUAGES = ("en", "ar")
DEFAULT_LANGUAGE = "en"
RTL_LANGUAGES = ("ar",)
LANGUAGE_COOKIE = "lang"

# Unicode "first strong isolate" ... "pop directional isolate". A value put
# into an Arabic sentence (an English citation, a number, a field name) is
# wrapped in these, so the browser lays it out on its own instead of
# reordering it with the Arabic words and punctuation around it.
_ISOLATE = "\u2068{}\u2069"

# key -> language -> text. {name} placeholders are filled in by t(); pass
# plain values (format numbers first). An Arabic text may leave out a
# placeholder its English text uses, but never add one.
TEXT: dict[str, dict[str, str]] = {
    # Both pages
    "nav.other_language": {"en": "العربية", "ar": "English"},
    "nav.other_code": {"en": "ar", "ar": "en"},
    "disclaimer": {
        "en": DISCLAIMER,
        "ar": "هذه أداة آلية لدعم القرار، وليست تقييماً سريرياً ولا تشخيصاً ولا وصفةً. تعرض "
        "المعلومات الناقصة في بيانات الحالة، وتقتبس ما تقوله الأدلة الإرشادية والأدلة التدريبية "
        "في مكتبة مصادرها عن مكوّنات الطرف الاصطناعي لهذه الحالة وتصميمه وتركيبه، مع درجة "
        "التوصية التي يحددها المصدر إن وُجدت. لا تختار المكوّنات ولا ترتّبها. لا تحكم على جاهزية "
        "المريض للتركيب. كل بند يحتاج إلى مراجعة مختص مؤهل في الأطراف الاصطناعية، والقرار له. "
        "قد تكون القوائم غير مكتملة: البند غير المدرج فُحص من حيث تعبئته فقط لا من حيث كفاية "
        "محتواه، ولا يُعرض إلا ما في مكتبة المصادر من بيانات.",
    },
    # Intake form
    "intake.page_title": {
        "en": "New Case Intake — AI Prosthetic Lab",
        "ar": "إدخال حالة جديدة — AI Prosthetic Lab",
    },
    "intake.heading": {"en": "New Case Intake", "ar": "إدخال حالة جديدة"},
    "intake.banner": {
        "en": "This tool lists missing intake information and quotes what published guidelines "
        "and manuals say about the case's prosthetic components, design and fitting. It does not "
        "diagnose, prescribe or choose components: the specialist decides.",
        "ar": "تعرض هذه الأداة المعلومات الناقصة في بيانات الحالة، وتقتبس ما تقوله الأدلة "
        "الإرشادية والأدلة التدريبية المنشورة عن مكوّنات الطرف الاصطناعي للحالة وتصميمه وتركيبه. "
        "لا تشخّص ولا تصف ولا تختار المكوّنات: القرار للمختص.",
    },
    "intake.not_saved": {"en": "Case not saved:", "ar": "لم تُحفظ الحالة:"},
    "intake.amputation": {"en": "Amputation", "ar": "البتر"},
    "intake.amputation_level": {"en": "Amputation level", "ar": "مستوى البتر"},
    "intake.select": {"en": "Select…", "ar": "اختر…"},
    "intake.side": {"en": "Side", "ar": "الجانب"},
    "intake.etiology": {"en": "Etiology", "ar": "سبب البتر"},
    "intake.not_recorded": {"en": "Not recorded", "ar": "لم يُسجَّل"},
    "intake.months_since_amputation": {"en": "Months since amputation", "ar": "عدد الأشهر منذ البتر"},
    "intake.demographics": {"en": "Demographics", "ar": "البيانات الديموغرافية"},
    "intake.age": {"en": "Age (years)", "ar": "العمر (بالسنوات)"},
    "intake.body_weight": {"en": "Body weight (kg)", "ar": "وزن الجسم (كغ)"},
    "intake.residual_limb": {"en": "Residual limb", "ar": "الطرف المتبقي"},
    "intake.wound_status": {"en": "Wound status", "ar": "حالة الجرح"},
    "intake.volume_stability": {"en": "Volume stability", "ar": "ثبات الحجم"},
    "intake.skin_condition": {"en": "Skin condition", "ar": "حالة الجلد"},
    "intake.length": {"en": "Residual limb length", "ar": "طول الطرف المتبقي"},
    "intake.pain": {"en": "Pain (residual limb / phantom)", "ar": "الألم (في الطرف المتبقي / ألم شبحي)"},
    "intake.sensation": {"en": "Sensation", "ar": "الإحساس"},
    "intake.activity": {"en": "Activity", "ar": "النشاط"},
    "intake.k_level": {"en": "K-level (lower limb only)", "ar": "المستوى الوظيفي K (للطرف السفلي فقط)"},
    "intake.activity_description": {
        "en": "Current activity (in patient's own terms)",
        "ar": "النشاط الحالي (بكلمات المريض نفسه)",
    },
    "intake.functional_goals": {"en": "Functional goals", "ar": "الأهداف الوظيفية"},
    "intake.prior_prostheses": {"en": "Prior prostheses", "ar": "الأطراف الاصطناعية السابقة"},
    "intake.no_prior": {
        "en": "No prior prosthesis (asked, none used)",
        "ar": "لا يوجد طرف اصطناعي سابق (سُئل المريض ولم يستخدم أياً منها)",
    },
    "intake.no_prior_hint": {
        "en": "Leave this section empty if device history wasn't asked.",
        "ar": "اترك هذا القسم فارغاً إذا لم يُسأل عن الأطراف السابقة.",
    },
    "intake.device": {"en": "Device {n}", "ar": "الجهاز {n}"},
    "intake.device_placeholder": {
        "en": "e.g. transtibial PTB socket, SACH foot",
        "ar": "مثال: تجويف PTB لبتر تحت الركبة، قدم SACH",
    },
    "intake.years_used": {"en": "Years used", "ar": "سنوات الاستخدام"},
    "intake.currently_using": {"en": "Currently using", "ar": "يستخدمه حالياً"},
    "intake.yes": {"en": "yes", "ar": "نعم"},
    "intake.no": {"en": "no", "ar": "لا"},
    "intake.device_issues": {
        "en": "Issues (fit, comfort, skin, mechanical)",
        "ar": "المشكلات (الملاءمة، الراحة، الجلد، الأعطال الميكانيكية)",
    },
    "intake.other_context": {"en": "Other context", "ar": "معلومات أخرى"},
    "intake.comorbidities": {
        "en": 'Comorbidities (one per line, or "none" if none)',
        "ar": "الأمراض المصاحبة (مرض في كل سطر، أو «لا يوجد» إن لم توجد)",
    },
    "intake.contralateral": {"en": "Contralateral limb status", "ar": "حالة الطرف المقابل"},
    "intake.cognitive": {"en": "Cognitive status", "ar": "الحالة الإدراكية"},
    "intake.notes": {"en": "Intake notes", "ar": "ملاحظات الإدخال"},
    "intake.submit": {"en": "Submit case", "ar": "إرسال الحالة"},
    # Review page
    "review.page_title": {
        "en": "Case Review — AI Prosthetic Lab",
        "ar": "مراجعة الحالة — AI Prosthetic Lab",
    },
    "review.heading": {"en": "Case Review — {case_id}", "ar": "مراجعة الحالة — {case_id}"},
    "review.not_searched": {
        "en": "The source library was not searched.",
        "ar": "لم يُبحث في مكتبة المصادر. التفاصيل التقنية:",
    },
    "review.saved": {"en": "Decision saved to the review log:", "ar": "حُفظ القرار في سجل المراجعة:"},
    "review.not_saved": {"en": "Decision not saved:", "ar": "لم يُحفظ القرار:"},
    "review.case": {"en": "Case", "ar": "الحالة"},
    "review.age": {"en": "Age", "ar": "العمر"},
    "review.none_used": {"en": "none used", "ar": "لم يستخدم أي طرف اصطناعي"},
    "review.years": {"en": "{years} years", "ar": "سنوات الاستخدام: {years}"},
    "review.in_use": {"en": "in use", "ar": "قيد الاستخدام"},
    "review.no_longer_used": {"en": "no longer used", "ar": "لم يعد مستخدَماً"},
    "review.issues": {"en": "issues:", "ar": "المشكلات:"},
    "review.gaps_heading": {"en": "Information gaps ({n})", "ar": "المعلومات الناقصة ({n})"},
    "review.similarity": {"en": "similarity {score}", "ar": "التشابه {score}"},
    "review.full_passage": {"en": "Full passage", "ar": "المقطع كاملاً"},
    "review.no_source": {"en": "No source cited.", "ar": "لم يُستشهد بأي مصدر."},
    "review.retrieved": {
        "en": "Passages retrieved for this field ({n})",
        "ar": "المقاطع المسترجعة لهذا البند ({n})",
    },
    "review.not_marked": {"en": "Not marked", "ar": "بلا تحديد"},
    "review.needed": {"en": "Needed", "ar": "مطلوب"},
    "review.not_needed": {"en": "Not needed for this case", "ar": "غير مطلوب لهذه الحالة"},
    "review.no_gaps": {
        "en": "No gaps identified: every listed intake field is filled in.",
        "ar": "لم تُحدَّد أي معلومات ناقصة: كل بنود الإدخال المدرجة مُعبَّأة.",
    },
    "review.decision_heading": {"en": "Reviewer decision", "ar": "قرار المختص"},
    "review.note_placeholder": {
        "en": "Note (required for Edit: what should change)",
        "ar": "ملاحظة (مطلوبة عند التعديل: ما الذي يجب تغييره)",
    },
    "review.approve": {"en": "Approve", "ar": "اعتماد"},
    "review.edit": {"en": "Edit", "ar": "تعديل"},
    "review.reject": {"en": "Reject", "ar": "رفض"},
    "review.logged_heading": {
        "en": "Logged decisions for this case ({n})",
        "ar": "القرارات المسجلة لهذه الحالة ({n})",
    },
    "review.log_saved_in": {"en": "Saved in", "ar": "محفوظة في"},
    "review.log_order": {
        "en": ", oldest first. Logged decisions are never changed.",
        "ar": "، الأقدم أولاً. لا تُغيَّر القرارات المسجلة أبداً.",
    },
    # Functional level and goals (reasoning/component_support.py)
    "functional.heading": {"en": "Functional level and goals", "ar": "المستوى الوظيفي والأهداف"},
    "functional.k_level": {"en": "Recorded K-level:", "ar": "المستوى الوظيفي المسجَّل (K):"},
    "functional.k_not_recorded": {"en": "not recorded", "ar": "لم يُسجَّل"},
    "functional.description": {
        "en": "How the source describes this level:",
        "ar": "وصف المصدر لهذا المستوى:",
    },
    "functional.cautions": {
        "en": "What the same source says about K-levels:",
        "ar": "ما يقوله المصدر نفسه عن مستويات K:",
    },
    "functional.all_levels": {"en": "All K-level descriptions (K0–K4)", "ar": "أوصاف كل المستويات (K0–K4)"},
    "functional.upper_limb": {
        "en": "K-levels describe the intended use of a lower-limb prosthesis, so none is shown "
        "for an upper-limb case.",
        "ar": "مستويات K تصف الاستخدام المقصود للطرف الاصطناعي السفلي، لذا لا يُعرض أي منها "
        "لحالة بتر في الطرف العلوي.",
    },
    "functional.activity": {"en": "Current activity (as recorded)", "ar": "النشاط الحالي (كما سُجِّل)"},
    "functional.goals": {"en": "Functional goals (as recorded)", "ar": "الأهداف الوظيفية (كما سُجِّلت)"},
    # Component statements
    "components.heading": {
        "en": "What the guidelines say about components ({n} statements)",
        "ar": "ما تقوله الأدلة الإرشادية عن المكوّنات ({n} بيانات)",
    },
    "components.intro": {
        "en": "Statements from the guidelines in the source library that apply to this case, "
        "quoted word for word with each guideline's own grade. They are not ranked and are not "
        "a prescription: the specialist decides.",
        "ar": "بيانات من الأدلة الإرشادية في مكتبة المصادر تنطبق على هذه الحالة، مقتبسة حرفياً "
        "مع درجة التوصية التي يحددها كل دليل. ليست مرتّبة وليست وصفة: القرار للمختص.",
    },
    "components.k_not_recorded": {
        "en": "Functional level (K-level) is not recorded, so statements that apply only at a "
        "specific K-level are not shown.",
        "ar": "المستوى الوظيفي (K) لم يُسجَّل، لذا لا تُعرض البيانات الخاصة بمستوى K محدد.",
    },
    "components.k0": {
        "en": "K0 is recorded, so statements about prosthetic or community ambulators are not "
        "shown: the CMS document describes K0 as no ability or potential to ambulate or "
        "transfer safely.",
        "ar": "سُجِّل المستوى K0، لذا لا تُعرض البيانات الخاصة بمن يمشون بالطرف الاصطناعي: تصف "
        "وثيقة CMS المستوى K0 بعدم القدرة أو الإمكانية على المشي أو الانتقال بأمان.",
    },
    "components.no_statement": {
        "en": "No statement in the source library covers this component for this case.",
        "ar": "لا يوجد في مكتبة المصادر بيان يتناول هذا المكوّن لهذه الحالة.",
    },
    "components.grade": {"en": "Source grade:", "ar": "درجة التوصية في المصدر:"},
    "components.same_source": {"en": "Same source, {pages}", "ar": "المصدر نفسه، {pages}"},
    "grade.Weak for": {"en": "Weak for", "ar": "ضعيفة لصالح"},
    "grade.Neither for nor against": {"en": "Neither for nor against", "ar": "لا لصالح ولا ضد"},
    "grade.none": {"en": "none given", "ar": "غير محددة"},
    # The brief's six kinds of source (catalog "source_type"), shown with each statement
    "source_type.protocol": {"en": "guideline or protocol", "ar": "دليل إرشادي أو بروتوكول"},
    "source_type.professional_knowledge": {
        "en": "professional knowledge (manual)",
        "ar": "معرفة مهنية (دليل تدريبي)",
    },
    "source_type.scientific_reference": {"en": "scientific reference", "ar": "مرجع علمي"},
    "source_type.applied_case": {"en": "applied case", "ar": "حالة تطبيقية"},
    "source_type.structured_data": {"en": "structured data", "ar": "بيانات منظمة"},
    "source_type.specialist_expertise": {"en": "specialist expertise", "ar": "خبرة المختصين"},
    "component.knee": {"en": "Knee unit", "ar": "وحدة الركبة"},
    "component.foot_ankle": {"en": "Foot and ankle", "ar": "القدم والكاحل"},
    "component.pylon": {"en": "Pylon", "ar": "الأنبوب الواصل (البايلون)"},
    "component.socket": {"en": "Socket", "ar": "التجويف (السوكيت)"},
    "component.interface": {
        "en": "Interface (liner or socket insert)",
        "ar": "الواجهة (البطانة أو الحشوة الداخلية)",
    },
    "component.suspension": {"en": "Suspension", "ar": "نظام التعليق"},
    "component.prosthesis_type": {"en": "Type of prosthesis", "ar": "نوع الطرف الاصطناعي"},
    "component.control_and_fit": {
        "en": "Control strategy, socket, suspension and components",
        "ar": "طريقة التحكم والتجويف والتعليق والمكوّنات",
    },
    # Design and fitting (reasoning/fitting_support.py)
    "fitting.heading": {
        "en": "What the sources say about design and fitting ({n} statements)",
        "ar": "ما تقوله المصادر عن التصميم والتركيب ({n} بيانات)",
    },
    "fitting.intro": {
        "en": "Statements from the guidelines and manuals in the source library on readiness for "
        "fitting, a preparatory or definitive prosthesis, fitting, and alignment, quoted word for "
        "word. They do not say whether this patient is ready, or how the prosthesis should be "
        "built or aligned: the specialist decides.",
        "ar": "بيانات من الأدلة الإرشادية والأدلة التدريبية في مكتبة المصادر عن الجاهزية للتركيب، "
        "والطرف الاصطناعي التمهيدي أو النهائي، والتركيب، والمحاذاة، مقتبسة حرفياً. لا تحدد ما إذا "
        "كان هذا المريض جاهزاً، ولا كيف يُصنع الطرف أو تُضبط محاذاته: القرار للمختص.",
    },
    "fitting.components_above": {
        "en": "Socket, interface and suspension are listed with the components above.",
        "ar": "التجويف والواجهة ونظام التعليق مدرجة مع المكوّنات أعلاه.",
    },
    "fitting.recorded": {
        "en": "Recorded at intake for this case (as entered, not judged):",
        "ar": "ما سُجِّل لهذه الحالة عند الإدخال (كما أُدخل، دون تقييم):",
    },
    "fitting.none_reported": {"en": "none reported", "ar": "لا يوجد"},
    "fitting.months": {"en": "{n} months", "ar": "عدد الأشهر: {n}"},
    "fitting.no_statement": {
        "en": "No statement in the source library covers this for this case.",
        "ar": "لا يوجد في مكتبة المصادر بيان يتناول هذا الجانب لهذه الحالة.",
    },
    "fitting_section.readiness": {"en": "Readiness for fitting", "ar": "الجاهزية للتركيب"},
    "fitting_section.prosthesis_stage": {
        "en": "Preparatory or definitive prosthesis",
        "ar": "طرف اصطناعي تمهيدي (مؤقت) أو نهائي",
    },
    "fitting_section.fitting": {
        "en": "Fitting, check-out and follow-up",
        "ar": "التركيب والفحص النهائي والمتابعة",
    },
    "fitting_section.alignment": {"en": "Alignment", "ar": "المحاذاة"},
    "review.relevant": {"en": "Relevant", "ar": "ذو صلة"},
    "review.not_relevant": {"en": "Not relevant for this case", "ar": "غير ذي صلة بهذه الحالة"},
    # A logged decision, as the log stores it
    "decision.approve": {"en": "approve", "ar": "اعتماد"},
    "decision.edit": {"en": "edit", "ar": "تعديل"},
    "decision.reject": {"en": "reject", "ar": "رفض"},
    # Per-gap judgements of one logged decision, e.g. "2 needed, 1 not needed"
    "summary.needed": {"en": "{n} needed", "ar": "مطلوب: {n}"},
    "summary.not_needed": {"en": "{n} not needed", "ar": "غير مطلوب: {n}"},
    "summary.not_marked": {"en": "{n} not marked", "ar": "بلا تحديد: {n}"},
    "summary.separator": {"en": ", ", "ar": "، "},
    "summary.no_gaps": {"en": "no gaps", "ar": "لا معلومات ناقصة"},
    "summary.components": {"en": "; components: ", "ar": "؛ المكوّنات: "},
    "summary.fitting": {"en": "; design and fitting: ", "ar": "؛ التصميم والتركيب: "},
    "summary.relevant": {"en": "{n} relevant", "ar": "ذو صلة: {n}"},
    "summary.not_relevant": {"en": "{n} not relevant", "ar": "غير ذي صلة: {n}"},
    # Language of a source document
    "doclang.en": {"en": "en", "ar": "إنجليزي"},
    "doclang.ar": {"en": "ar", "ar": "عربي"},
    "doclang.de": {"en": "de", "ar": "ألماني"},
    # Gap status (shared/field_guide.py NOT_RECORDED, RECORDED_UNKNOWN)
    "status.not recorded": {"en": "not recorded", "ar": "لم يُسجَّل"},
    "status.recorded as unknown": {"en": "recorded as unknown", "ar": "سُجِّل غير معروف"},
    # Why a gap is listed (reasoning/gap_analysis.py). Never a diagnosis or
    # recommendation, in either language.
    "gap.not_recorded": {
        "en": "{label} was not recorded at intake.",
        "ar": "لم يُسجَّل البند «{label}» عند إدخال الحالة.",
    },
    "gap.recorded_unknown": {
        "en": "{label} was recorded as unknown.",
        "ar": "سُجِّل البند «{label}» على أنه غير معروف.",
    },
    "gap.no_source": {
        "en": "No passage in the source library was found on this topic, so whether it is "
        "needed is for the specialist to judge.",
        "ar": "لم يُعثر في مكتبة المصادر على مقطع يتناول هذا الموضوع، لذا فتقدير الحاجة "
        "إليه متروك للمختص.",
    },
    # Arabic leaves the citation out: a long English title wrapped inside an
    # Arabic sentence is hard to read (seen 2026-10-08), and the citation is
    # shown on its own line right below the quote.
    "gap.cited": {
        "en": "{citation} discusses this topic (quoted below); check whether it applies to this case.",
        "ar": "يتناول المصدر المذكور أدناه هذا الموضوع (انظر الاقتباس)؛ تحقَّق مما إذا كان "
        "ينطبق على هذه الحالة.",
    },
    # Errors a reviewer can cause from the pages
    "error.required.amputation_level": {"en": "amputation_level is required", "ar": "مستوى البتر مطلوب"},
    "error.required.side": {"en": "side is required", "ar": "الجانب مطلوب"},
    "error.yes_no": {
        "en": "expected yes or no, got {value!r}",
        "ar": "القيمة المتوقعة «نعم» أو «لا»، والمُرسَلة «{value}»",
    },
    "error.device_details_only": {
        "en": "prior device {n}: describe the device, not only its details",
        "ar": "الجهاز السابق {n}: صِف الجهاز نفسه، لا تفاصيله فقط",
    },
    "error.device_invalid": {"en": "prior device {n}: {detail}", "ar": "الجهاز السابق {n}: {detail}"},
    "error.no_prior_but_device": {
        "en": '"No prior prosthesis" is ticked, but a device is described',
        "ar": "خيار «لا يوجد طرف اصطناعي سابق» محدَّد، لكن وُصف جهاز",
    },
    "error.unknown_decision": {
        "en": "Unknown decision {decision!r}: expected approve, edit or reject.",
        "ar": "قرار غير معروف «{decision}»: المتوقع اعتماد أو تعديل أو رفض.",
    },
    "error.edit_needs_note": {
        "en": "An edit needs a note saying what should change.",
        "ar": "التعديل يحتاج إلى ملاحظة توضح ما الذي يجب تغييره.",
    },
    "error.not_a_gap": {
        "en": "{field!r} is not one of this case's gaps.",
        "ar": "البند «{field}» ليس من المعلومات الناقصة في هذه الحالة.",
    },
    "error.unknown_judgement": {
        "en": "Unknown judgement {judgement!r} for {field!r}.",
        "ar": "تقدير غير معروف «{judgement}» للبند «{field}».",
    },
    "error.not_a_statement": {
        "en": "{statement!r} is not one of the statements shown for this case.",
        "ar": "البيان «{statement}» ليس من البيانات المعروضة لهذه الحالة.",
    },
}

# The Arabic names of the intake fields that can be gaps (English:
# FieldInfo.label in shared/field_guide.py).
FIELD_LABELS: dict[str, dict[str, str]] = {
    "ar": {
        "residual_limb.wound_status": "حالة جرح الطرف المتبقي",
        "residual_limb.volume_stability": "ثبات حجم الطرف المتبقي",
        "residual_limb.skin_condition": "حالة جلد الطرف المتبقي",
        "residual_limb.length_description": "طول الطرف المتبقي وشكله",
        "residual_limb.pain": "ألم الطرف المتبقي والألم الشبحي",
        "residual_limb.sensation": "الإحساس في الطرف المتبقي",
        "activity.k_level": "المستوى الوظيفي (K)",
        "activity.description": "النشاط والتنقل الحاليان",
        "activity.functional_goals": "الأهداف الوظيفية",
        "prior_devices": "استخدام أطراف اصطناعية سابقة",
        "comorbidities": "الأمراض المصاحبة",
        "contralateral_limb_status": "حالة الطرف المقابل",
        "cognitive_status": "الحالة الإدراكية",
        "etiology": "سبب البتر",
        "months_since_amputation": "المدة منذ البتر",
        "age_years": "العمر",
        "body_weight_kg": "وزن الجسم",
    },
}

# The Arabic names of the choices in shared/case_schema.py, by enum class.
# (English shows the stored value itself, e.g. "knee disarticulation".)
VALUE_LABELS: dict[str, dict[str, dict[str, str]]] = {
    "ar": {
        "AmputationLevel": {
            "partial_foot": "بتر جزئي في القدم",
            "syme": "بتر سايم (عند الكاحل)",
            "transtibial": "بتر تحت الركبة",
            "knee_disarticulation": "فصل مفصل الركبة",
            "transfemoral": "بتر فوق الركبة",
            "hip_disarticulation": "فصل مفصل الورك",
            "partial_hand": "بتر جزئي في اليد",
            "wrist_disarticulation": "فصل مفصل الرسغ",
            "transradial": "بتر تحت المرفق",
            "elbow_disarticulation": "فصل مفصل المرفق",
            "transhumeral": "بتر فوق المرفق",
            "shoulder_disarticulation": "فصل مفصل الكتف",
        },
        "Side": {"left": "أيسر", "right": "أيمن", "bilateral": "ثنائي الجانب"},
        "Etiology": {
            "vascular": "وعائي",
            "trauma": "رضّي (إصابة)",
            "oncologic": "ورمي",
            "infection": "عدوى",
            "congenital": "خَلقي",
            "other": "سبب آخر",
            "unknown": "غير معروف",
        },
        "ActivityLevel": {
            "K0": "K0", "K1": "K1", "K2": "K2", "K3": "K3", "K4": "K4", "unknown": "غير معروف",
        },
        "WoundStatus": {
            "healed": "ملتئم", "healing": "قيد الالتئام", "open": "مفتوح", "unknown": "غير معروف",
        },
        "VolumeStability": {"stable": "مستقر", "fluctuating": "متذبذب", "unknown": "غير معروف"},
    },
}


def t(key: str, lang: str, **params) -> str:
    """The text for `key` in `lang`, with its {placeholders} filled in."""
    template = TEXT[key][lang]  # a KeyError here is a missing translation (see tests)
    if lang in RTL_LANGUAGES:
        params = {name: _ISOLATE.format(value) for name, value in params.items()}
    return template.format(**params)


def placeholders(template: str) -> set[str]:
    """The {names} a text uses, e.g. {"n"} for "Device {n}"."""
    return {name for _, name, _, _ in Formatter().parse(template) if name}


def field_label(path: str, lang: str) -> str:
    """The reviewer-facing name of a gap field, e.g. "residual_limb.pain"."""
    if lang == "en":
        return FIELDS_BY_PATH[path].label
    return FIELD_LABELS[lang][path]


def value_label(member, lang: str) -> str:
    """How a choice from shared/case_schema.py (e.g. Side.LEFT) is shown."""
    if lang == "en":
        return member.value.replace("_", " ")
    return VALUE_LABELS[lang][type(member).__name__][member.value]


def text_direction(lang: str) -> str:
    return "rtl" if lang in RTL_LANGUAGES else "ltr"


def language_from_cookies(cookies) -> str:
    """The language the reviewer chose, or the default if none (or an unknown one)."""
    lang = cookies.get(LANGUAGE_COOKIE)
    return lang if lang in LANGUAGES else DEFAULT_LANGUAGE


class TranslatableError(ValueError):
    """An error the pages can show in the reviewer's language.

    str(error) is the English message, so tests, logs and code that knows
    nothing about languages see the same text as before.
    """

    def __init__(self, key: str, **params):
        self.key = key
        self.params = params
        super().__init__(self.message("en"))

    def message(self, lang: str) -> str:
        # A wrapped error (e.g. a device row's own error) is translated too.
        params = {
            name: value.message(lang) if isinstance(value, TranslatableError) else value
            for name, value in self.params.items()
        }
        return t(self.key, lang, **params)


def error_message(error: Exception, lang: str) -> str:
    """The message to show for an error: translated if it can be."""
    return error.message(lang) if isinstance(error, TranslatableError) else str(error)
