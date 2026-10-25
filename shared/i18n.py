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
  python -m knowledge.ingest").

The review log stays in English (field labels, gap explanations) and records
the language the reviewer saw as "ui_language", so entries can be compared
whichever language was used.
"""

from string import Formatter

from shared.config import DISCLAIMER, ORTHOTIC_DISCLAIMER
from shared.field_guide import FIELDS_BY_PATH

LANGUAGES = ("en", "ar")
DEFAULT_LANGUAGE = "en"
RTL_LANGUAGES = ("ar",)
LANGUAGE_COOKIE = "lang"
LANGUAGE_COOKIE_DAYS = 365

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
    "nav.language": {"en": "Language", "ar": "اللغة"},
    "disclaimer": {
        "en": DISCLAIMER,
        "ar": "نموذج أوّلي للبحث، لم يُتحقَّق من صلاحيته للاستخدام السريري. "
        "هذه أداة آلية لدعم القرار، وليست تقييماً سريرياً ولا تشخيصاً ولا وصفةً. تعرض "
        "المعلومات الناقصة في بيانات الحالة، وما تقوله الأدلة الإرشادية والأدلة التدريبية في مكتبة "
        "مصادرها عن مكوّنات الطرف الاصطناعي لهذه الحالة وتصميمه وتركيبه. كل ملخص قصير يكتبه نموذج "
        "لغوي للذكاء الاصطناعي وقد يكون خاطئاً؛ وتحته نص المصدر نفسه، مُتحقَّق منه حرفياً "
        "مقابل المقطع، مع درجة التوصية التي يحددها المصدر إن وُجدت. قارن كل ملخص باقتباسه. لا تختار "
        "المكوّنات ولا ترتّبها. لا تحكم على جاهزية المريض للتركيب. كل بند يحتاج إلى مراجعة مختص "
        "مؤهل في الأطراف الاصطناعية، والقرار له. قد تكون القوائم غير مكتملة: البند غير المدرج فُحص "
        "من حيث تعبئته فقط لا من حيث كفاية محتواه، ولا يُستخدم إلا ما وجده البحث في مكتبة المصادر.",
    },
    # AI summaries (reasoning/rag.py). The reason the AI is unavailable is
    # shown as it is, in English (a technical message).
    "ai.label": {"en": "AI summary — check it against the quote below:",
                 "ar": "ملخص بالذكاء الاصطناعي — قارنه بالاقتباس أدناه:"},
    "ai.unavailable": {
        "en": "AI summaries are not available for {part}:",
        "ar": "ملخصات الذكاء الاصطناعي غير متاحة لقسم {part}. التفاصيل التقنية:",
    },
    "ai.unavailable_after": {
        "en": "The passages the search found are listed without summaries.",
        "ar": "تُعرض المقاطع التي وجدها البحث دون ملخصات.",
    },
    "ai_part.gaps": {"en": "the information gaps", "ar": "المعلومات الناقصة"},
    "ai_part.components": {"en": "the functional level and components", "ar": "المستوى الوظيفي والمكوّنات"},
    "ai_part.fitting": {"en": "design and fitting", "ar": "التصميم والتركيب"},
    "ai.removed": {
        "en": "{n} AI summary or summaries removed by the checks (for example, a quote not found word for "
        "word in its passage); each reason is kept in the log.",
        "ar": "حذفت عمليات التحقق من ملخصات الذكاء الاصطناعي: {n} (مثلاً لأن الاقتباس لم يوجد حرفياً في "
        "مقطعه)؛ وسبب كل حذف محفوظ في السجل.",
    },
    "ai.passages_found": {
        "en": "Passages the search found for this section, not summarised ({n})",
        "ar": "المقاطع التي وجدها البحث لهذا القسم، دون تلخيص ({n})",
    },
    "ai.no_passages": {
        "en": "The search found no passage for this section.",
        "ar": "لم يجد البحث أي مقطع لهذا القسم.",
    },
    # A section the AI answered for but that has no summary: what code knows, never what the sources say.
    "ai.topic_nothing_reported": {
        "en": "No AI summary for this section: the AI reported nothing from the passages the search found. "
        "Check them below.",
        "ar": "لا يوجد ملخص بالذكاء الاصطناعي لهذا القسم: لم يذكر الذكاء الاصطناعي شيئاً من المقاطع التي "
        "وجدها البحث. راجعها أدناه.",
    },
    "ai.topic_all_removed": {
        "en": "No AI summary for this section: the checks removed the AI's {n} summary or summaries for it "
        "(each reason is kept in the log). Check the passages the search found below.",
        "ar": "لا يوجد ملخص بالذكاء الاصطناعي لهذا القسم: حذفت عمليات التحقق ملخصاته له (عددها: {n}؛ وسبب "
        "كل حذف محفوظ في السجل). راجع المقاطع التي وجدها البحث أدناه.",
    },
    "ai.topic_shown_elsewhere": {
        "en": "No AI summary for this section: the AI gave it only a quote that is already shown under an "
        "earlier section. Check the passages the search found below.",
        "ar": "لا يوجد ملخص بالذكاء الاصطناعي لهذا القسم: لم يقدّم له الذكاء الاصطناعي إلا اقتباساً معروضاً "
        "بالفعل تحت قسم سابق. راجع المقاطع التي وجدها البحث أدناه.",
    },
    "review.attribution": {"en": "{authors}; licence: {licence}", "ar": "{authors}؛ الترخيص: {licence}"},
    "ai.written_by": {
        "en": "AI summaries on this page were written by {models} (prompt version {version}).",
        "ar": "كتب ملخصات الذكاء الاصطناعي في هذه الصفحة: {models} (إصدار التعليمات {version}).",
    },
    # Intake form
    "intake.page_title": {
        "en": "New Case Intake — AI Prosthetic Lab",
        "ar": "إدخال حالة جديدة — AI Prosthetic Lab",
    },
    "intake.heading": {"en": "New Case Intake", "ar": "إدخال حالة جديدة"},
    "intake.banner": {
        "en": "This tool lists missing intake information and shows what published guidelines "
        "and manuals say about the case's prosthetic components, design and fitting: short AI "
        "summaries, each with the source's own words quoted below it. It does not diagnose, "
        "prescribe or choose components: the specialist decides.",
        "ar": "تعرض هذه الأداة المعلومات الناقصة في بيانات الحالة، وما تقوله الأدلة الإرشادية "
        "والأدلة التدريبية المنشورة عن مكوّنات الطرف الاصطناعي للحالة وتصميمه وتركيبه: ملخصات "
        "قصيرة بالذكاء الاصطناعي، تحت كل منها نص المصدر نفسه مقتبساً. لا تشخّص ولا تصف ولا تختار "
        "المكوّنات: القرار للمختص.",
    },
    "intake.ai_note": {
        "en": "After you submit, the analysis takes about a minute: an AI language model in a "
        "cloud service summarises the passages the search finds. Only the amputation level, side "
        "and recorded K-level are sent to that service with the passages, not what you type; "
        "still, enter test data only.",
        "ar": "بعد الإرسال يستغرق التحليل نحو دقيقة: يلخّص نموذج لغوي للذكاء الاصطناعي في خدمة "
        "سحابية المقاطع التي يجدها البحث. لا يُرسَل إلى تلك الخدمة مع المقاطع إلا مستوى البتر "
        "والجانب والمستوى الوظيفي المسجَّل (K)، لا ما تكتبه؛ ومع ذلك أدخل بيانات اختبارية فقط.",
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
    # Functional level and goals (prosthetics/component_support.py)
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
    "functional.from_sources": {
        "en": "What the sources say about the functional level:",
        "ar": "ما تقوله المصادر عن المستوى الوظيفي:",
    },
    "review.made_before_ai": {
        "en": "This case was analysed before the AI summaries were added, so its functional level, "
        "component and fitting sections are not available. Submit the case again to see them.",
        "ar": "حُلِّلت هذه الحالة قبل إضافة ملخصات الذكاء الاصطناعي، لذا أقسام المستوى الوظيفي "
        "والمكوّنات والتركيب غير متاحة لها. أرسل الحالة مجدداً لعرضها.",
    },
    # Component statements
    "components.heading": {
        "en": "What the sources say about components ({n} statements)",
        "ar": "ما تقوله المصادر عن المكوّنات ({n} بيانات)",
    },
    "components.intro": {
        "en": "Short summaries written by an AI from the passages the search found in the source "
        "library, each with the source's own words quoted below it (checked word for word) and "
        "the source's grade where it prints one. They are not ranked and are not a prescription: "
        "the specialist decides.",
        "ar": "ملخصات قصيرة كتبها الذكاء الاصطناعي من المقاطع التي وجدها البحث في مكتبة المصادر، "
        "تحت كل منها نص المصدر نفسه مقتبساً (مُتحقَّقاً منه حرفياً) مع درجة التوصية إن ذكرها "
        "المصدر. ليست مرتّبة وليست وصفة: القرار للمختص.",
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
    "components.grade": {"en": "Source grade:", "ar": "درجة التوصية في المصدر:"},
    "components.same_source": {"en": "Same source, {pages}", "ar": "المصدر نفسه، {pages}"},
    "grade.Strong for": {"en": "Strong for", "ar": "قوية لصالح"},
    "grade.Weak for": {"en": "Weak for", "ar": "ضعيفة لصالح"},
    "grade.Neither for nor against": {"en": "Neither for nor against", "ar": "لا لصالح ولا ضد"},
    "grade.Weak against": {"en": "Weak against", "ar": "ضعيفة ضد"},
    "grade.Strong against": {"en": "Strong against", "ar": "قوية ضد"},
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
    # Design and fitting (prosthetics/fitting_support.py)
    "fitting.heading": {
        "en": "What the sources say about design and fitting ({n} statements)",
        "ar": "ما تقوله المصادر عن التصميم والتركيب ({n} بيانات)",
    },
    "fitting.intro": {
        "en": "Short AI summaries of what the guidelines and manuals in the source library say on "
        "readiness for fitting, a preparatory or definitive prosthesis, fitting, and alignment, each "
        "with the source's own words quoted below it (checked word for word). They do not say "
        "whether this patient is ready, or how the prosthesis should be built or aligned: the "
        "specialist decides.",
        "ar": "ملخصات قصيرة بالذكاء الاصطناعي لما تقوله الأدلة الإرشادية والأدلة التدريبية في مكتبة "
        "المصادر عن الجاهزية للتركيب، والطرف الاصطناعي التمهيدي أو النهائي، والتركيب، والمحاذاة، تحت "
        "كل منها نص المصدر نفسه مقتبساً (مُتحقَّقاً منه حرفياً). لا تحدد ما إذا كان هذا المريض "
        "جاهزاً، ولا كيف يُصنع الطرف أو تُضبط محاذاته: القرار للمختص.",
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
    # A form value that can't be used; {field} is the form's own label.
    "error.whole_number": {"en": "{field}: enter a whole number.", "ar": "{field}: أدخل عدداً صحيحاً."},
    "error.number": {"en": "{field}: enter a number.", "ar": "{field}: أدخل رقماً."},
    "error.not_negative": {"en": "{field}: enter 0 or more.", "ar": "{field}: أدخل صفراً أو أكثر."},
    "error.positive": {
        "en": "{field}: enter a number greater than 0.",
        "ar": "{field}: أدخل رقماً أكبر من صفر.",
    },
    "error.unknown_choice": {
        "en": "{field}: choose one of the listed options.",
        "ar": "{field}: اختر أحد الخيارات المعروضة.",
    },
    # Any other value the form can't read (the details go to the server log).
    "error.invalid_input": {
        "en": "A value could not be read. Check the form and try again.",
        "ar": "تعذّرت قراءة إحدى القيم. راجع النموذج وحاول مرة أخرى.",
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
    # ---- Orthotics (use case 03, stroke AFO; added 2026-10-22) ----
    # The Arabic clinical terms here still need checking by an Arabic-reading orthotist.
    "disclaimer.orthotics": {
        "en": ORTHOTIC_DISCLAIMER,
        "ar": "نموذج أوّلي للبحث، لم يُتحقَّق من صلاحيته للاستخدام السريري. "
        "هذه أداة آلية لدعم القرار، وليست تقييماً سريرياً ولا تشخيصاً ولا وصفةً. تعرض "
        "المعلومات الناقصة في بيانات الحالة، وما تقوله الأدلة الإرشادية والأدلة التدريبية في مكتبة "
        "مصادرها عن أجهزة تقويم الكاحل والقدم والتنبيه الكهربائي الوظيفي، وعن تصميم الجهاز التقويمي "
        "وتركيبه، لهذه الحالة. كل ملخص قصير يكتبه نموذج لغوي للذكاء الاصطناعي وقد يكون خاطئاً؛ وتحته "
        "نص المصدر نفسه، مُتحقَّق منه حرفياً مقابل المقطع، مع درجة التوصية التي يحددها المصدر إن وُجدت. "
        "قارن كل ملخص باقتباسه. لا تختار الأجهزة ولا ترتّبها، ولا تحدد الزوايا أو مدة الارتداء، ولا "
        "تقول إن كان هذا المريض يحتاج إلى جهاز تقويمي أو تنبيه كهربائي. كل بند يحتاج إلى مراجعة "
        "أخصائي تقويم مؤهل، والقرار له. حقول الإدخال الخاصة بالتقويم وما عُلِّم منها بأنه حرج مسوّدةٌ "
        "تنتظر مراجعة المالك وأخصائي تقويم. قد تكون القوائم غير مكتملة: لا يُستخدم إلا ما وجده البحث "
        "في مكتبة المصادر.",
    },
    "intake.orthotic_link": {
        "en": "Orthotic case instead (stroke, ankle-foot orthosis) →",
        "ar": "حالة تقويمية بدلاً من ذلك (سكتة دماغية، جهاز تقويم الكاحل والقدم) ←",
    },
    "ort.prosthetic_link": {"en": "Prosthetic case instead →", "ar": "حالة طرف اصطناعي بدلاً من ذلك ←"},
    "ort.page_title": {
        "en": "New Orthotic Case — AI Prosthetic Lab",
        "ar": "حالة تقويمية جديدة — مختبر الأطراف الاصطناعية بالذكاء الاصطناعي",
    },
    "ort.heading": {
        "en": "New Orthotic Case: stroke, ankle-foot orthosis",
        "ar": "حالة تقويمية جديدة: سكتة دماغية، جهاز تقويم الكاحل والقدم",
    },
    "ort.banner": {
        "en": "This tool lists missing intake information and shows what published guidelines and manuals say "
              "about ankle-foot orthoses and FES, and about orthosis design and fitting, for this case: short AI "
              "summaries, each with the source's own words quoted below it. It does not diagnose, prescribe, "
              "choose a device or set its angles: the orthotist decides.",
        "ar": "تعرض هذه الأداة المعلومات الناقصة في بيانات الحالة، وما تقوله الأدلة الإرشادية والأدلة التدريبية "
              "المنشورة عن أجهزة تقويم الكاحل والقدم والتنبيه الكهربائي الوظيفي، وعن تصميم الجهاز التقويمي "
              "وتركيبه، لهذه الحالة: ملخصات قصيرة بالذكاء الاصطناعي، تحت كل منها نص المصدر نفسه مقتبساً. "
              "لا تشخّص ولا تصف ولا تختار الجهاز ولا تحدد زواياه: القرار لأخصائي التقويم.",
    },
    "ort.draft_note": {
        "en": "These orthotic fields, and which are marked critical, are a draft awaiting review by the owner "
              "and an orthotist.",
        "ar": "هذه الحقول التقويمية، وما عُلِّم منها بأنه حرج، مسوّدة تنتظر مراجعة المالك وأخصائي تقويم.",
    },
    "ort.ai_note": {
        "en": "After you submit, the analysis takes about a minute: an AI language model in a cloud service "
              "summarises the passages the search finds. Only the condition, the affected side and the months "
              "since onset are sent to that service with the passages, not what you type; still, enter test "
              "data only.",
        "ar": "بعد الإرسال يستغرق التحليل نحو دقيقة: يلخّص نموذج لغوي للذكاء الاصطناعي في خدمة سحابية المقاطع "
              "التي يجدها البحث. لا يُرسَل إلى تلك الخدمة مع المقاطع إلا الحالة المرضية والجانب المصاب وعدد "
              "الأشهر منذ بدء الحالة، لا ما تكتبه؛ ومع ذلك أدخل بيانات اختبارية فقط.",
    },
    "ort.case": {"en": "Condition", "ar": "الحالة المرضية"},
    "ort.condition": {"en": "Condition", "ar": "الحالة المرضية"},
    "ort.side": {"en": "Affected side", "ar": "الجانب المصاب"},
    "ort.months_since_onset": {"en": "Months since onset", "ar": "عدد الأشهر منذ بدء الحالة"},
    "ort.functional_goals": {"en": "Functional goals", "ar": "الأهداف الوظيفية"},
    "ort.walking": {"en": "Walking", "ar": "المشي"},
    "ort.walking_status": {"en": "Walking status", "ar": "حالة المشي"},
    "ort.walking_aid": {"en": "Walking aid", "ar": "أداة المساعدة على المشي"},
    "ort.gait_speed": {"en": "Gait speed (m/s)", "ar": "سرعة المشي (م/ث)"},
    "ort.gait_speed_test": {"en": "Test used for gait speed", "ar": "الاختبار المستخدم لقياس سرعة المشي"},
    "ort.gait_speed_hint": {
        "en": "Name the test with every speed, e.g. 10-metre walk test, comfortable pace.",
        "ar": "اذكر الاختبار مع كل سرعة، مثل اختبار المشي لعشرة أمتار بالسرعة المريحة.",
    },
    "ort.falls": {"en": "Falls in the past 6 months", "ar": "مرات السقوط في الأشهر الستة الماضية"},
    "ort.gait": {"en": "Gait, observed phase by phase", "ar": "المشية، مرحلةً مرحلة كما لوحظت"},
    "ort.gait_hint": {
        "en": "Tick what you saw. Tick \"observed, none of these\" if gait was observed without any of them; "
              "leave all empty if gait was not observed.",
        "ar": "علِّم ما لاحظته. علِّم «لوحظت، دون أيٍّ مما يلي» إن لوحظت المشية دون أيٍّ منها؛ واترك الكل "
              "فارغاً إن لم تُلاحَظ المشية.",
    },
    "ort.no_deviations": {"en": "Observed, none of these", "ar": "لوحظت، دون أيٍّ مما يلي"},
    "ort.other_deviations": {"en": "Other deviations", "ar": "انحرافات أخرى"},
    "ort.exam": {"en": "Examination", "ar": "الفحص"},
    "ort.df_knee_ext": {
        "en": "Ankle dorsiflexion, knee extended (degrees)",
        "ar": "العطف الظهري للكاحل والركبة ممدودة (بالدرجات)",
    },
    "ort.df_knee_flex": {
        "en": "Ankle dorsiflexion, knee flexed (degrees)",
        "ar": "العطف الظهري للكاحل والركبة مثنية (بالدرجات)",
    },
    "ort.angle_hint": {
        "en": "Passive range. Dorsiflexion is positive; an ankle that stops short of neutral is negative, e.g. -5.",
        "ar": "المدى السلبي. العطف الظهري موجب؛ والكاحل الذي يقف قبل الوضع المحايد سالب، مثل ‎-5‎.",
    },
    "ort.tone_scale": {"en": "Plantarflexor tone: scale", "ar": "توتر العضلات المثنية للأخمص: المقياس"},
    "ort.tone_grade": {"en": "Plantarflexor tone: grade", "ar": "توتر العضلات المثنية للأخمص: الدرجة"},
    "ort.tone_notes": {"en": "Tone: position and rater", "ar": "التوتر: وضعية القياس ومن قاس"},
    "ort.tone_hint": {
        "en": "A grade is only kept with its scale.",
        "ar": "لا تُحفَظ الدرجة إلا مع مقياسها.",
    },
    "ort.df_strength": {"en": "Dorsiflexor strength", "ar": "قوة العضلات العاطفة الظهرية"},
    "ort.ke_strength": {"en": "Knee extensor strength", "ar": "قوة باسطات الركبة"},
    "ort.knee_in_stance": {"en": "Knee in stance", "ar": "الركبة في مرحلة الارتكاز"},
    "ort.foot_posture": {"en": "Foot posture (flexible or rigid)", "ar": "وضعية القدم (مرنة أو متيبسة)"},
    "ort.protective_sensation": {"en": "Protective sensation of the foot", "ar": "الإحساس الوقائي في القدم"},
    "ort.proprioception": {"en": "Proprioception", "ar": "الحس العميق"},
    "ort.skin": {"en": "Skin of the foot and leg", "ar": "جلد القدم والساق"},
    "ort.devices": {"en": "Footwear and devices", "ar": "الحذاء والأجهزة"},
    "ort.footwear": {"en": "Footwear", "ar": "الحذاء"},
    "ort.donning": {"en": "Putting an orthosis on", "ar": "ارتداء الجهاز التقويمي"},
    "ort.prior_orthoses": {"en": "Previous orthoses or FES", "ar": "أجهزة تقويمية أو تنبيه كهربائي سابق"},
    "ort.no_prior": {
        "en": "No previous orthosis or FES (asked, none used)",
        "ar": "لا جهاز تقويمي ولا تنبيه كهربائي سابق (سُئل، ولم يُستخدم أي منها)",
    },
    "ort.no_prior_hint": {
        "en": "Leave this section empty if device history wasn't asked.",
        "ar": "اترك هذا القسم فارغاً إن لم يُسأل عن الأجهزة السابقة.",
    },
    "ort.device_placeholder": {
        "en": "e.g. prefabricated posterior leaf spring AFO",
        "ar": "مثلاً: جهاز تقويم الكاحل والقدم الجاهز ذو النابض الخلفي",
    },
    "ort.implanted": {
        "en": "Implanted electronic device (asked only if FES is discussed)",
        "ar": "جهاز إلكتروني مزروع (يُسأل عنه فقط عند مناقشة التنبيه الكهربائي)",
    },
    "ort.requirements": {
        "en": "What the orthosis must do (one per line)",
        "ar": "ما يجب أن يؤديه الجهاز التقويمي (بند في كل سطر)",
    },
    "ort.requirements_hint": {
        "en": "Written by the orthotist, e.g. \"clear the toes in swing\". The tool never writes these.",
        "ar": "يكتبها أخصائي التقويم، مثل «رفع أصابع القدم عن الأرض في مرحلة الأرجحة». لا تكتبها الأداة أبداً.",
    },
    "ort.options_heading": {
        "en": "What the sources say about ankle-foot orthoses and FES ({n})",
        "ar": "ما تقوله المصادر عن أجهزة تقويم الكاحل والقدم والتنبيه الكهربائي ({n})",
    },
    "ort.options_intro": {
        "en": "Short summaries written by an AI from the passages the search found in the source library, each "
              "with the source's own words quoted below it (checked word for word) and the source's grade where "
              "it prints one. Shown side by side and never ranked: the orthotist chooses, and writes the choice "
              "and the reason in the decision note.",
        "ar": "ملخصات قصيرة كتبها الذكاء الاصطناعي من المقاطع التي وجدها البحث في مكتبة المصادر، تحت كل منها نص "
              "المصدر نفسه مقتبساً (مُتحقَّقاً منه حرفياً) مع درجة التوصية إن ذكرها المصدر. تُعرَض جنباً إلى "
              "جنب ولا تُرتَّب أبداً: يختار أخصائي التقويم، ويكتب اختياره وسببه في ملاحظة القرار.",
    },
    "ort.design_heading": {
        "en": "What the sources say about design and fitting ({n})",
        "ar": "ما تقوله المصادر عن التصميم والتركيب ({n})",
    },
    "ort.design_intro": {
        "en": "Short AI summaries of what the guidelines and manuals say on orthosis design, fitting and check-out, "
              "timing and training, and outcome measures, each with the source's own words quoted below it "
              "(checked word for word). They do not set angles, materials or wearing times for this patient: "
              "the orthotist decides.",
        "ar": "ملخصات قصيرة بالذكاء الاصطناعي لما تقوله الأدلة الإرشادية والأدلة التدريبية عن تصميم الجهاز التقويمي "
              "وتركيبه وفحصه، وتوقيته والتدريب عليه، ومقاييس النتائج، تحت كل منها نص المصدر نفسه مقتبساً "
              "(مُتحقَّقاً منه حرفياً). لا تحدد الزوايا أو المواد أو مدة الارتداء لهذا المريض: القرار لأخصائي التقويم.",
    },
    "ort.requirements_heading": {
        "en": "What the orthosis must do, as the orthotist wrote it",
        "ar": "ما يجب أن يؤديه الجهاز التقويمي، كما كتبه أخصائي التقويم",
    },
    "ort.requirements_none": {"en": "Not written yet.", "ar": "لم يُكتب بعد."},
    "ort.deviations_heading": {"en": "Gait deviations by phase, as recorded", "ar": "انحرافات المشية حسب المرحلة، كما سُجِّلت"},
    "ort.not_observed": {"en": "Gait not observed.", "ar": "لم تُلاحَظ المشية."},
    "ort.none_observed": {"en": "Observed, none of the listed deviations.", "ar": "لوحظت، دون أيٍّ من الانحرافات المدرجة."},
    "ort.critical": {"en": "critical (draft)", "ar": "حرج (مسوّدة)"},
    "ort.degrees": {"en": "{n}°", "ar": "{n}°"},
    "phase.initial_contact": {"en": "Initial contact", "ar": "التلامس الأولي"},
    "phase.loading_response": {"en": "Loading response", "ar": "استجابة التحميل"},
    "phase.mid_stance": {"en": "Mid-stance", "ar": "منتصف الارتكاز"},
    "phase.terminal_stance": {"en": "Terminal stance", "ar": "نهاية الارتكاز"},
    "phase.pre_swing": {"en": "Pre-swing", "ar": "ما قبل الأرجحة"},
    "phase.swing": {"en": "Swing", "ar": "الأرجحة"},
    "component.afo_or_fes": {"en": "AFO or FES for walking", "ar": "جهاز تقويم الكاحل والقدم أو التنبيه الكهربائي للمشي"},
    "component.afo_types": {"en": "Types of ankle-foot orthosis", "ar": "أنواع أجهزة تقويم الكاحل والقدم"},
    "component.effects_limits": {"en": "Effects and their limits", "ar": "التأثيرات وحدودها"},
    "component.cautions": {"en": "When not to provide, and cautions", "ar": "متى لا يُقدَّم الجهاز، والاحتياطات"},
    "fitting_section.design": {"en": "Design: ankle angle, stiffness, trim lines, materials",
                               "ar": "التصميم: زاوية الكاحل والصلابة وخطوط القص والمواد"},
    "fitting_section.orthosis_fitting": {"en": "Fitting and check-out", "ar": "التركيب والفحص"},
    "fitting_section.timing_training": {"en": "Timing and training with the orthosis",
                                        "ar": "التوقيت والتدريب على الجهاز التقويمي"},
    "fitting_section.outcome_measures": {"en": "Outcome measures", "ar": "مقاييس النتائج"},
    "ai_part.devices": {"en": "the ankle-foot orthosis and FES options", "ar": "خيارات جهاز تقويم الكاحل والقدم والتنبيه الكهربائي"},
    "ai_part.design_fitting": {"en": "design and fitting", "ar": "التصميم والتركيب"},
    "summary.orthotic_options": {"en": "; orthosis and FES: ", "ar": "؛ الجهاز التقويمي والتنبيه الكهربائي: "},
    "error.required.condition": {"en": "condition is required", "ar": "الحالة المرضية مطلوبة"},
    "error.angle": {
        "en": "{field}: enter degrees between -90 and 90.",
        "ar": "{field}: أدخل عدد الدرجات بين ‎-90‎ و‎90‎.",
    },
    "error.tone_needs_scale": {
        "en": "A plantarflexor tone grade needs its scale: choose the scale.",
        "ar": "درجة توتر العضلات المثنية للأخمص تحتاج إلى مقياسها: اختر المقياس.",
    },
    "error.speed_needs_test": {
        "en": "A gait speed needs the test it was measured with: name the test.",
        "ar": "سرعة المشي تحتاج إلى الاختبار الذي قيست به: اذكر الاختبار.",
    },
    "error.no_deviations_but_ticked": {
        "en": "\"Observed, none of these\" is ticked, but deviations are ticked too.",
        "ar": "عُلِّم «لوحظت، دون أيٍّ مما يلي»، لكن عُلِّمت انحرافات أيضاً.",
    },
    "error.no_prior_orthosis_but_device": {
        "en": "\"No previous orthosis or FES\" is ticked, but a device is described.",
        "ar": "عُلِّم «لا جهاز تقويمي ولا تنبيه كهربائي سابق»، لكن وُصف جهاز.",
    },
    # ---- Orthotic modules after the analysis (2026-10-23; orthotics/modules.py, the canvas's design) ----
    "mod.map": {"en": "Map", "ar": "الخريطة"},
    "mod.analyse": {"en": "1 Analyse", "ar": "1 التحليل"},
    "mod.requirements": {"en": "2 Requirements", "ar": "2 المتطلبات"},
    "mod.options": {"en": "3 Options", "ar": "3 الخيارات"},
    "mod.design": {"en": "4 Digital design", "ar": "4 التصميم الرقمي"},
    "mod.needs_case": {"en": "Open an orthotic case first", "ar": "افتح حالة تقويمية أولاً"},
    "mod.case": {"en": "Case {id}", "ar": "الحالة {id}"},
    "mod.side": {"en": "{side} side affected", "ar": "الجانب المصاب: {side}"},
    "mod.months": {"en": "{n} months since onset", "ar": "الأشهر منذ البداية: {n}"},
    "mod.age": {"en": "Age {n}", "ar": "العمر {n}"},
    "mod.weight": {"en": "{n} kg", "ar": "{n} كغ"},
    "mod.fake_data": {"en": "Test case · fake data", "ar": "حالة اختبار · بيانات وهمية"},
    "mod.orthotist_decides": {"en": "Decision support: the orthotist decides", "ar": "دعم القرار: أخصائي التقويم هو من يقرر"},
    "mod.draft": {
        "en": "Draft: these modules, their lists of device types, parts, steps and parameters, and their wording "
              "await review by the owner and an orthotist. Every requirement, option, mark, choice and parameter "
              "is the orthotist's; the tool writes, suggests and ranks none of them.",
        "ar": "مسوّدة: هذه الوحدات وقوائم أنواع الأجهزة والمكونات والخطوات والمعايير وصياغتها بانتظار مراجعة المالك "
              "وأخصائي تقويم. كل متطلب وخيار وتقدير واختيار ومعيار هو من أخصائي التقويم؛ لا تكتب الأداة شيئاً منها ولا "
              "تقترحه ولا ترتّبه.",
    },
    "mod.saved": {"en": "Saved.", "ar": "حُفظ."},
    "mod.passages_note": {
        "en": "Below each item: passages the local search found in the source library that mention it, quoted as "
              "printed with their page. They are not summarised and not checked to support this case: read them and "
              "judge whether they apply.",
        "ar": "تحت كل بند: مقاطع وجدها البحث المحلي في مكتبة المصادر وتذكره، منقولة كما طُبعت مع صفحتها. لم تُلخَّص ولم "
              "يُتحقق من أنها تدعم هذه الحالة: اقرأها وقدّر ما إذا كانت تنطبق.",
    },
    "mod.no_passage": {"en": "No passage in the source library mentions this.", "ar": "لا يذكر هذا أيُّ مقطع في مكتبة المصادر."},
    # The system map (the canvas's "System map", rebuilt 2026-10-23).
    "map.title": {"en": "Orthotics module — system map", "ar": "وحدة تقويم العظام — خريطة النظام"},
    "map.intro": {
        "en": "Function first, device second. Every screen hangs off one step of this chain, and the orthotist "
              "decides at each step.",
        "ar": "الوظيفة أولاً ثم الجهاز. كل شاشة مرتبطة بخطوة من هذه السلسلة، وأخصائي التقويم يقرر في كل خطوة.",
    },
    "map.chain_heading": {"en": "The reasoning chain", "ar": "سلسلة الاستدلال"},
    "map.decides": {"en": "The orthotist decides at every step.", "ar": "أخصائي التقويم يقرر في كل خطوة."},
    "map.principle": {
        "en": "The system shows options, evidence and checks: never a prescription.",
        "ar": "يعرض النظام الخيارات والأدلة والفحوص: لا وصفة أبداً.",
    },
    "map.loop_back": {
        "en": "Findings loop back: follow-up returns to tuning, redesign or re-assessment.",
        "ar": "النتائج تعود إلى البداية: تعيد المتابعة إلى الضبط أو إعادة التصميم أو إعادة التقييم.",
    },
    "map.module": {"en": "Module {n}", "ar": "الوحدة {n}"},
    "map.modules_heading": {"en": "Six modules, mapped to the brief's capabilities", "ar": "ست وحدات مربوطة بقدرات الموجز"},
    "map.open_screen": {"en": "Open screen {n} →", "ar": "افتح الشاشة {n} ←"},
    "map.new_case": {"en": "New orthotic case", "ar": "حالة تقويمية جديدة"},
    "map.in_brief": {"en": "In the brief:", "ar": "في الموجز:"},  # the prosthetics map
    "map.from_case": {
        "en": "Opened from an orthotic case's pages, in the header.",
        "ar": "تُفتح من صفحات الحالة التقويمية، من الشريط العلوي.",
    },
    "map.latest": {
        "en": "The links open case {id}, the orthotic case saved last.",
        "ar": "تفتح الروابط الحالة {id}، وهي آخر حالة تقويمية حُفظت.",
    },
    "map.knowledge_heading": {"en": "The knowledge behind it", "ar": "المعرفة التي يقوم عليها"},
    "map.safety_heading": {"en": "Safety built in", "ar": "السلامة مدمجة"},
    "map.rollout_heading": {"en": "Roll-out", "ar": "التوسّع"},
    "map.rollout_title": {"en": "One condition and device at a time", "ar": "حالة مرضية وجهاز واحد في كل مرة"},
    "map.rollout_now": {"en": "built, as a draft", "ar": "مبنيّ كمسوّدة"},
    "chain.impairments": {"en": "Impairments and goals", "ar": "الإعاقات والأهداف"},
    "chain.gait": {"en": "Problems by gait phase", "ar": "المشكلات حسب مرحلة المشي"},
    "chain.requirements": {"en": "What the orthosis must do", "ar": "ما يجب أن يؤديه الجهاز"},
    "chain.options": {"en": "Design options", "ar": "خيارات التصميم"},
    "chain.fabrication": {"en": "Fabrication", "ar": "التصنيع"},
    "chain.fit": {"en": "Fit and tune", "ar": "التركيب والضبط"},
    "chain.training": {"en": "Training with it", "ar": "التدريب على الجهاز"},
    "chain.follow_up": {"en": "Follow-up", "ar": "المتابعة"},
    "chain_module.impairments": {"en": "Module 1 · case analysis", "ar": "الوحدة 1 · تحليل الحالة"},
    "chain_module.gait": {"en": "Module 1 · gait observation", "ar": "الوحدة 1 · ملاحظة المشي"},
    "chain_module.requirements": {"en": "Module 2 · requirements", "ar": "الوحدة 2 · المتطلبات"},
    "chain_module.options": {"en": "Module 3 · options, not orders", "ar": "الوحدة 3 · خيارات لا أوامر"},
    "chain_module.fabrication": {"en": "Module 4 · digital or conventional", "ar": "الوحدة 4 · رقمي أو تقليدي"},
    "chain_module.fit": {"en": "Module 5 · check-out, tuning", "ar": "الوحدة 5 · الفحص والضبط"},
    "chain_module.training": {"en": "Module 5 · rehabilitation link", "ar": "الوحدة 5 · الربط بالتأهيل"},
    "chain_module.follow_up": {"en": "Module 6 · outcomes over time", "ar": "الوحدة 6 · النتائج عبر الزمن"},
    "map_name.analysis": {"en": "Functional case analysis", "ar": "تحليل الحالة الوظيفية"},
    "map_name.requirements": {"en": "Functional requirements", "ar": "المتطلبات الوظيفية"},
    "map_name.options": {"en": "Design options", "ar": "خيارات التصميم"},
    "map_name.design": {"en": "Digital design", "ar": "التصميم الرقمي"},
    "map_name.fit": {"en": "Fit, tune and train", "ar": "التركيب والضبط والتدريب"},
    "map_name.follow_up": {"en": "Follow-up", "ar": "المتابعة"},
    "map_does.analysis": {
        "en": "Condition modules, a structured exam with named scales and how each value was measured, and gait "
              "observed phase by phase.",
        "ar": "وحدات الحالات المرضية، وفحص منظّم بمقاييس مسمّاة وبطريقة قياس كل قيمة، والمشي ملاحظاً مرحلةً مرحلة.",
    },
    "map_does.requirements": {
        "en": "Each problem becomes what the orthosis must do. Conflicts between requirements are shown, not hidden.",
        "ar": "تصبح كل مشكلة ما يجب أن يؤديه الجهاز. وتُعرض التعارضات بين المتطلبات ولا تُخفى.",
    },
    "map_does.options": {
        "en": "Two or three configurations side by side, with materials tied to the person and the clinic.",
        "ar": "تكوينان أو ثلاثة جنباً إلى جنب، مع مواد مرتبطة بالشخص وبالعيادة.",
    },
    "map_does.design": {
        "en": "Scan, rectify, set parameters, simulate, manufacture. Every parameter is versioned.",
        "ar": "المسح والتعديل وتحديد المعايير والمحاكاة والتصنيع. ولكل معيار نسخ محفوظة.",
    },
    "map_does.fit": {
        "en": "Check-out list, tuning with before and after walking measures, training plan, Arabic leaflet.",
        "ar": "قائمة الفحص عند التسليم، والضبط مع مقاييس المشي قبل وبعد، وخطة التدريب، والنشرة العربية.",
    },
    "map_does.follow_up": {
        "en": "Outcome measures over time, skin and wearing time, alerts that loop back to tuning or redesign.",
        "ar": "مقاييس النتائج عبر الزمن، والجلد ومدة الارتداء، وتنبيهات تعيد إلى الضبط أو إعادة التصميم.",
    },
    "req.title": {"en": "What the orthosis must do", "ar": "ما يجب أن يؤديه جهاز التقويم"},
    "req.intro": {
        "en": "Each requirement is a function, never a device, written by the orthotist and tied to the case findings "
              "it comes from. The orthotist sets the priority; the tool writes none of them.",
        "ar": "كل متطلب وظيفةٌ لا جهاز، يكتبه أخصائي التقويم ويربطه بنتائج الحالة التي جاء منها. يحدد أخصائي التقويم "
              "الأولوية؛ ولا تكتب الأداة شيئاً منها.",
    },
    "req.col_from": {"en": "From the case", "ar": "من الحالة"},
    "req.col_requirement": {"en": "Requirement", "ar": "المتطلب"},
    "req.col_priority": {"en": "Priority", "ar": "الأولوية"},
    "req.requirement": {"en": "Requirement", "ar": "المتطلب"},
    "req.findings": {"en": "Findings it comes from ({n} ticked)", "ar": "النتائج التي جاء منها (المعلَّم: {n})"},
    "req.new": {"en": "New", "ar": "جديد"},
    "req.priority_unset": {"en": "Not set", "ar": "غير محددة"},
    "req.empty_removes": {
        "en": "Write a new requirement in an empty row. Empty a requirement's text to remove it.",
        "ar": "اكتب متطلباً جديداً في صف فارغ. أفرغ نص متطلبٍ لحذفه.",
    },
    "req.save": {"en": "Save the requirements", "ar": "احفظ المتطلبات"},
    "req.missing_none": {"en": "None listed.", "ar": "لا شيء مُدرج."},
    "req.traceable_heading": {"en": "Traceable", "ar": "قابل للتتبع"},
    "req.traceable": {
        "en": "Each requirement keeps the findings it came from. On the options page each material and part is tied "
              "to the requirements it serves, so every part leads back to the case.",
        "ar": "يحتفظ كل متطلب بالنتائج التي جاء منها. وفي صفحة الخيارات يُربط كل مادة ومكوّن بالمتطلبات التي يخدمها، "
              "فيعود كل مكوّن إلى الحالة.",
    },
    "req.to_options": {"en": "See design options →", "ar": "اطّلع على خيارات التصميم ←"},
    "req.back": {"en": "← Back to the case analysis", "ar": "→ العودة إلى تحليل الحالة"},
    "req_group.gait": {"en": "Gait, by phase", "ar": "المشي حسب المرحلة"},
    "req_group.exam": {"en": "Exam", "ar": "الفحص"},
    "req_group.other": {"en": "Goals, walking and other", "ar": "الأهداف والمشي وغيرها"},
    "priority.must": {"en": "Must", "ar": "ضروري"},
    "priority.should": {"en": "Should", "ar": "مهم"},
    "priority.nice": {"en": "Nice to have", "ar": "مستحسن"},
    "review.to_requirements": {"en": "Module 2: what the orthosis must do →", "ar": "الوحدة 2: ما يجب أن يؤديه الجهاز ←"},
    "options.title": {"en": "Design options", "ar": "خيارات التصميم"},
    "options.intro": {
        "en": "Shown side by side, never ranked. The orthotist chooses and records why.",
        "ar": "تُعرض جنباً إلى جنب دون ترتيب. يختار أخصائي التقويم ويسجّل السبب.",
    },
    "options.requirements": {"en": "Requirements (module 2)", "ar": "المتطلبات (الوحدة 2)"},
    "options.no_requirements": {
        "en": "No requirements yet: write them first, so each option can be marked against them.",
        "ar": "لا متطلبات بعد: اكتبها أولاً ليُقدَّر كل خيار مقابلها.",
    },
    "options.option": {"en": "Option {id}", "ar": "الخيار {id}"},
    "options.chosen_mark": {"en": "chosen", "ar": "المختار"},
    "options.unaddressed": {
        "en": "Marked by the orthotist as not addressing a Must requirement: {ids}",
        "ar": "قدّر أخصائي التقويم أنه لا يلبّي متطلباً ضرورياً: {ids}",
    },
    "options.addresses": {"en": "Addresses (the orthotist's marks)", "ar": "ما يلبّيه (تقدير أخصائي التقويم)"},
    "options.mark_unset": {"en": "not marked", "ar": "غير مقدَّر"},
    "options.parts": {"en": "Materials and parts, and what each serves", "ar": "المواد والمكونات وما يخدمه كلٌّ منها"},
    "options.part": {"en": "Material or part {n}", "ar": "المادة أو المكوّن {n}"},
    "options.serves": {"en": "Serves", "ar": "يخدم"},
    "options.no_parts": {"en": "None listed.", "ar": "لا شيء مُدرج."},
    "options.notes": {
        "en": "Notes: costs to the patient, checks at fitting",
        "ar": "ملاحظات: ما يكلّفه للمريض، وما يُفحص عند التركيب",
    },
    "options.sources": {"en": "What the source library says", "ar": "ما تقوله مكتبة المصادر"},
    "options.edit_heading": {"en": "Write or change the options", "ar": "اكتب الخيارات أو عدّلها"},
    "options.edit_note": {
        "en": "Leave an option's device type empty to leave it out. Only the fixed words of the lists are searched; "
              "nothing typed here is sent anywhere.",
        "ar": "اترك نوع جهاز الخيار فارغاً لحذفه. لا يُبحث إلا عن الكلمات الثابتة في القوائم؛ ولا يُرسل شيء مما يُكتب "
              "هنا إلى أي جهة.",
    },
    "options.device": {"en": "Device type", "ar": "نوع الجهاز"},
    "options.none": {"en": "None", "ar": "لا شيء"},
    "options.save": {"en": "Save the options", "ar": "احفظ الخيارات"},
    "options.choice_heading": {"en": "The orthotist's choice", "ar": "اختيار أخصائي التقويم"},
    "options.choose": {"en": "Option chosen", "ar": "الخيار المختار"},
    "options.reason": {"en": "Reason (required)", "ar": "السبب (مطلوب)"},
    "options.choice_note": {
        "en": "Recorded with the requirements and the evidence shown at the time.",
        "ar": "يُسجَّل مع المتطلبات والأدلة المعروضة حينها.",
    },
    "options.record": {"en": "Record the choice", "ar": "سجّل الاختيار"},
    "options.chosen_logged": {"en": "The choice is recorded in the review log.", "ar": "سُجِّل الاختيار في سجل المراجعة."},
    "options.logged": {"en": "Choices recorded ({n})", "ar": "الاختيارات المسجّلة ({n})"},
    "options.to_design": {"en": "Digital design →", "ar": "التصميم الرقمي ←"},
    "mark.yes": {"en": "yes", "ar": "نعم"},
    "mark.partly": {"en": "partly", "ar": "جزئياً"},
    "mark.no": {"en": "no", "ar": "لا"},
    "decision.design_choice": {"en": "design choice", "ar": "اختيار التصميم"},
    "device.solid_afo": {"en": "Solid (rigid) AFO", "ar": "جهاز تقويم صلب للكاحل والقدم"},
    "device.hinged_afo": {"en": "Hinged AFO, ankle joints and plantarflexion stop",
                          "ar": "جهاز تقويم مفصلي للكاحل والقدم بمفاصل كاحل ومانع للانثناء الأخمصي"},
    "device.flexible_afo": {"en": "Flexible AFO", "ar": "جهاز تقويم مرن للكاحل والقدم"},
    "device.posterior_leaf_spring": {"en": "Posterior leaf spring AFO", "ar": "جهاز تقويم بنابض ورقي خلفي"},
    "device.carbon_afo": {"en": "Carbon AFO", "ar": "جهاز تقويم من ألياف الكربون"},
    "device.anterior_shell_afo": {"en": "Anterior shell (anti-talus) AFO", "ar": "جهاز تقويم بغلاف أمامي (مضاد للكاحل)"},
    "device.printed_afo": {"en": "3D-printed AFO", "ar": "جهاز تقويم مطبوع ثلاثي الأبعاد"},
    "device.prefabricated_afo": {"en": "Prefabricated AFO", "ar": "جهاز تقويم جاهز الصنع"},
    "device.fes": {"en": "FES, peroneal nerve stimulation (with the rehabilitation team)",
                   "ar": "التنبيه الكهربائي الوظيفي للعصب الشظوي (مع فريق التأهيل)"},
    "part.polypropylene_shell": {"en": "Polypropylene shell", "ar": "غلاف من البولي بروبيلين"},
    "part.carbon_composite": {"en": "Carbon composite", "ar": "مركّب ألياف الكربون"},
    "part.printed_shell": {"en": "3D-printed shell (nylon, TPU)", "ar": "غلاف مطبوع ثلاثي الأبعاد (نايلون، TPU)"},
    "part.eva_lining": {"en": "EVA foam lining", "ar": "بطانة من رغوة EVA"},
    "part.ankle_joints": {"en": "Ankle joints", "ar": "مفاصل الكاحل"},
    "part.plantarflexion_stop": {"en": "Plantarflexion stop", "ar": "مانع الانثناء الأخمصي"},
    "part.posterior_reinforcement": {"en": "Posterior reinforcement", "ar": "تقوية خلفية"},
    "part.straps": {"en": "Straps and closure", "ar": "الأحزمة والإغلاق"},
    "part.heel_wedge": {"en": "Heel wedge", "ar": "إسفين الكعب"},
    "part.footwear": {"en": "Footwear", "ar": "الحذاء"},
    "design.title": {"en": "Digital design", "ar": "التصميم الرقمي"},
    "design.no_choice": {"en": "No option chosen yet.", "ar": "لم يُختَر خيار بعد."},
    "design.steps_heading": {"en": "Workflow", "ar": "سير العمل"},
    "design.status": {"en": "Status", "ar": "الحالة"},
    "design.method": {"en": "Method", "ar": "الطريقة"},
    "design.method_unset": {"en": "Not recorded", "ar": "غير مسجَّلة"},
    "design.notes": {"en": "Notes", "ar": "ملاحظات"},
    "design.step_sources": {"en": "What the source library says about this step", "ar": "ما تقوله مكتبة المصادر عن هذه الخطوة"},
    "design.save_steps": {"en": "Save the workflow", "ar": "احفظ سير العمل"},
    "design.parameters_heading": {"en": "Design parameters", "ar": "معايير التصميم"},
    "design.parameters_note": {
        "en": "As set by the orthotist, kept as typed.",
        "ar": "كما يحددها أخصائي التقويم، وتُحفظ كما كُتبت.",
    },
    "design.version_note": {"en": "What changed (optional)", "ar": "ما الذي تغيّر (اختياري)"},
    "design.save_parameters": {"en": "Save as a new version", "ar": "احفظ نسخةً جديدة"},
    "design.versions": {"en": "Versions ({n})", "ar": "النسخ ({n})"},
    "design.current": {"en": "current", "ar": "الحالية"},
    "design.values": {"en": "Values ({n})", "ar": "القيم ({n})"},
    "design.no_versions": {"en": "No version saved yet.", "ar": "لم تُحفظ نسخة بعد."},
    "step.capture": {"en": "Capture", "ar": "أخذ الشكل"},
    "step.rectify": {"en": "Rectify", "ar": "التعديل"},
    "step.parameters": {"en": "Parameters", "ar": "المعايير"},
    "step.fabricate": {"en": "Manufacture", "ar": "التصنيع"},
    "step.release": {"en": "Release", "ar": "التسليم"},
    "step_status.not_started": {"en": "Not started", "ar": "لم تبدأ"},
    "step_status.in_progress": {"en": "In progress", "ar": "قيد التنفيذ"},
    "step_status.done": {"en": "Done", "ar": "منجزة"},
    "step_status.not_needed": {"en": "Not needed", "ar": "غير لازمة"},
    "method.plaster_cast": {"en": "Plaster cast", "ar": "قالب جبسي"},
    "method.scan_3d": {"en": "3D scan", "ar": "مسح ثلاثي الأبعاد"},
    "method.measurements": {"en": "Measurements only", "ar": "قياسات فقط"},
    "method.plaster_model": {"en": "On the plaster model", "ar": "على النموذج الجبسي"},
    "method.cad": {"en": "Digital (CAD)", "ar": "رقمياً (CAD)"},
    "method.thermoforming": {"en": "Thermoforming", "ar": "التشكيل الحراري"},
    "method.printing_3d": {"en": "3D printing", "ar": "الطباعة ثلاثية الأبعاد"},
    "method.prefabricated": {"en": "Prefabricated", "ar": "جاهز الصنع"},
    "param.ankle_angle": {"en": "Ankle angle", "ar": "زاوية الكاحل"},
    "param.plantarflexion_stop": {"en": "Plantarflexion stop", "ar": "مانع الانثناء الأخمصي"},
    "param.trim_lines": {"en": "Trim lines", "ar": "خطوط القص"},
    "param.footplate": {"en": "Footplate", "ar": "صفيحة القدم"},
    "param.shell": {"en": "Shell material and thickness", "ar": "مادة الغلاف وسماكته"},
    "param.lining": {"en": "Lining", "ar": "البطانة"},
    "param.closure": {"en": "Closure", "ar": "الإغلاق"},
    "param.joints": {"en": "Joints", "ar": "المفاصل"},
    "param.heel_wedge": {"en": "Heel wedge or shoe", "ar": "إسفين الكعب أو الحذاء"},
    "error.too_long": {"en": "{field}: at most {n} characters.", "ar": "{field}: {n} حرفاً على الأكثر."},
    "error.too_many_requirements": {"en": "At most {n} requirements.", "ar": "{n} متطلباً على الأكثر."},
    "error.option_needs_device": {
        "en": "Option {option}: choose its device type, or clear its parts, marks and notes.",
        "ar": "الخيار {option}: اختر نوع جهازه، أو امسح مكوناته وتقديراته وملاحظاته.",
    },
    "error.part_needs_choice": {
        "en": "Option {option}: a requirement is ticked for a material or part that isn't chosen.",
        "ar": "الخيار {option}: عُلِّم متطلب لمادة أو مكوّن لم يُختر.",
    },
    "error.choice_needs_option": {"en": "Choose one of the options.", "ar": "اختر أحد الخيارات."},
    "error.choice_needs_reason": {"en": "Write the reason for the choice.", "ar": "اكتب سبب الاختيار."},
    "error.no_parameter_change": {
        "en": "Nothing changed since the last version: no new version saved.",
        "ar": "لم يتغير شيء منذ النسخة الأخيرة: لم تُحفظ نسخة جديدة.",
    },
    # ---- The orthotic screens of the design canvas (2026-10-23; orthotics/modules.py, hard_stops.py, fit.py,
    # followup.py): module 1's analysis page, modules 5-6, the hard stops, the knowledge boxes ----
    "mod.fit": {"en": "5 Fit & tune", "ar": "5 التركيب والضبط"},
    "mod.follow_up": {"en": "6 Follow-up", "ar": "6 المتابعة"},
    "mod.design_version": {"en": "Design v{n}", "ar": "التصميم، النسخة {n}"},
    "mod.delivered": {"en": "Delivered {date}", "ar": "سُلِّم في {date}"},
    "mod.pseudonymous": {"en": "Pseudonymous id only, no identifiers", "ar": "معرّف مستعار فقط، دون بيانات تعريفية"},
    "mod.orthotist_approves": {
        "en": "The orthotist sets and approves each value",
        "ar": "يحدد أخصائي التقويم كل قيمة ويعتمدها",
    },
    "mod.one_per_line": {"en": "(one per line)", "ar": "(بند في كل سطر)"},
    "lang_name.ar": {"en": "العربية", "ar": "العربية"},
    "lang_name.en": {"en": "English", "ar": "الإنجليزية"},
    "know.guidelines": {"en": "Guidelines", "ar": "الأدلة الإرشادية"},
    "know.manuals": {"en": "Technical manuals", "ar": "الأدلة التقنية"},
    "know.graph": {"en": "Design knowledge graph", "ar": "شبكة معرفة التصميم"},
    "know.cases": {"en": "Case library", "ar": "مكتبة الحالات"},
    "know.expertise": {"en": "Clinic expertise", "ar": "خبرة العيادة"},
    "know.data": {"en": "Structured data", "ar": "البيانات المنظمة"},
    "know.glossary": {"en": "Arabic glossary", "ar": "المسرد العربي"},
    "know_does.guidelines": {"en": "Graded, per condition", "ar": "مصنّفة الدرجة، لكل حالة مرضية"},
    "know_does.manuals": {"en": "Practice, labelled as no outcome evidence", "ar": "ممارسة، موسومة بأنها بلا دليل على النتائج"},
    "know_does.graph": {"en": "Deficit → requirement → feature → evidence", "ar": "القصور ← المتطلب ← الخاصية ← الدليل"},
    "know_does.cases": {"en": "Similar cases and how they went", "ar": "حالات مشابهة وكيف سارت"},
    "know_does.expertise": {"en": "Owned, versioned rules", "ar": "قواعد مملوكة ومحفوظة بنسخها"},
    "know_does.data": {"en": "Measures, devices, local stock", "ar": "المقاييس والأجهزة والمخزون المحلي"},
    "know_does.glossary": {"en": "Terms and patient leaflets", "ar": "المصطلحات ونشرات المرضى"},
    "know_here.guidelines": {
        "en": "In the library: the VA/DoD stroke guideline, WHO's rehabilitation package and NICE HTG178, searched locally.",
        "ar": "في المكتبة: دليل VA/DoD للسكتة الدماغية، وحزمة التأهيل من منظمة الصحة العالمية، وإرشاد NICE HTG178، ويُبحث فيها محلياً.",
    },
    "know_here.manuals": {
        "en": "The ICRC AFO manual: its passages carry that label on the option cards.",
        "ar": "دليل اللجنة الدولية للصليب الأحمر لأجهزة تقويم الكاحل والقدم: تحمل مقاطعه هذا الوسم في بطاقات الخيارات.",
    },
    "know_here.graph": {
        "en": "Here: finding → requirement (module 2) → part (module 3) → the source's passages.",
        "ar": "هنا: النتيجة ← المتطلب (الوحدة 2) ← المكوّن (الوحدة 3) ← مقاطع المصدر.",
    },
    "know_here.cases": {"en": "Not built yet.", "ar": "لم تُبنَ بعد."},
    "know_here.expertise": {
        "en": "The clinic's hard-stop rules below, each with its status (drafts await the owner's approval), and the owner's rule table for the evidence.",
        "ar": "قواعد التوقف الإلزامي للعيادة أدناه، ولكلٍّ منها حالتها (المسوّدات بانتظار موافقة المالك)، وجدول قواعد المالك للأدلة.",
    },
    "know_here.data": {
        "en": "As the orthotist enters them: measures at each visit, the clinic's stock on each option.",
        "ar": "كما يُدخلها أخصائي التقويم: المقاييس في كل زيارة، ومخزون العيادة لكل خيار.",
    },
    "know_here.glossary": {
        "en": "The page's Arabic terms, for an Arabic-reading orthotist to check; leaflets written by the orthotist.",
        "ar": "مصطلحات الصفحة العربية، ليراجعها أخصائي تقويم يقرأ العربية؛ والنشرات يكتبها أخصائي التقويم.",
    },
    "rollout.stroke_afo": {"en": "Stroke AFO", "ar": "جهاز تقويم الكاحل والقدم بعد السكتة الدماغية"},
    "rollout.cp_afo": {"en": "Cerebral palsy AFO", "ar": "جهاز تقويم الكاحل والقدم في الشلل الدماغي"},
    "rollout.diabetic_foot": {"en": "Diabetic foot footwear and offloading", "ar": "أحذية القدم السكرية وتخفيف الحمل عنها"},
    "rollout.scoliosis_kafo": {
        "en": "Scoliosis bracing, KAFO after spinal cord injury",
        "ar": "مشدّات الجنف، وجهاز تقويم الركبة والكاحل والقدم بعد إصابة الحبل الشوكي",
    },
    "rollout.digital": {"en": "Digital design", "ar": "التصميم الرقمي"},
    # The hard stops (orthotics/hard_stops.py): the rules as the design's map words them. Each one's status
    # (a draft awaiting the owner, or the clinic's rule) comes from data/knowledge/clinic_rules.csv and is
    # shown beside it (hard.status_*). Every line quotes the rule; none says in the tool's own voice what to do.
    "hard.heading": {
        "en": "Hard stops: a rule that matches routes the case to a doctor",
        "ar": "التوقفات الإلزامية: القاعدة التي تنطبق تحيل الحالة إلى طبيب",
    },
    "hard.draft_rules": {
        "en": "Draft rules from the design's system map, awaiting the owner's approval: they are not the clinic's rules yet. The tool only looks up what the intake records and never infers a value; the orthotist and the doctor decide.",
        "ar": "قواعد مسوّدة من خريطة النظام في التصميم، بانتظار موافقة المالك: ليست قواعد العيادة بعد. تكتفي الأداة بالنظر فيما تسجّله استمارة الحالة ولا تستنتج أي قيمة؛ والقرار لأخصائي التقويم وللطبيب.",
    },
    "hard.clinic_rules": {
        "en": "Rules set and versioned by the clinic. The tool only looks up what the intake records and never infers a value; a rule that matches routes the case to a person, who decides.",
        "ar": "قواعد تضعها العيادة وتحدّد إصداراتها. تكتفي الأداة بالنظر فيما تسجّله استمارة الحالة ولا تستنتج أي قيمة؛ والقاعدة التي تنطبق تحيل الحالة إلى شخص هو من يقرّر.",
    },
    "hard.status_draft": {
        "en": "Draft rule, awaiting the owner's approval",
        "ar": "قاعدة مسوّدة بانتظار موافقة المالك",
    },
    "hard.status_approved": {
        "en": "Clinic rule, version {version}, approved by {owner} on {date}",
        "ar": "قاعدة العيادة، الإصدار {version}، اعتمدها {owner} في {date}",
    },
    "hard.checks_heading": {"en": "Hard-stop checks", "ar": "فحوص التوقف الإلزامي"},
    "hard.stop_banner": {
        "en": "A hard-stop rule matches what was recorded; the rule routes the case to a doctor:",
        "ar": "تنطبق على ما سُجِّل قاعدة توقف إلزامي، وهي تحيل الحالة إلى طبيب:",
    },
    "hard.ulcer": {"en": "Ulcer, infection or poor blood supply", "ar": "قرحة أو عدوى أو ضعف التروية الدموية"},
    "hard.insensate": {"en": "Reduced sensation", "ar": "ضعف الإحساس"},
    "hard.contracture": {"en": "Calf shortness, dorsiflexion with the knee extended", "ar": "قِصَر الساق، الانثناء الظهري والركبة ممدودة"},
    "hard.fes_implant": {"en": "FES with an implanted device", "ar": "التنبيه الكهربائي مع جهاز مزروع"},
    "hard_rule.ulcer": {"en": "Ulcer with infection or poor blood supply", "ar": "قرحة مع عدوى أو ضعف في التروية الدموية"},
    "hard_rule.insensate": {
        "en": "A rigid device on insensate skin without pressure relief",
        "ar": "جهاز صلب على جلد فاقد للإحساس دون تخفيف للضغط",
    },
    "hard_rule.contracture": {
        "en": "Fixed contracture beyond what the design can accommodate",
        "ar": "تقفّع ثابت يتجاوز ما يستطيع التصميم استيعابه",
    },
    "hard_rule.fes_implant": {"en": "FES with an implanted electronic device", "ar": "التنبيه الكهربائي الوظيفي مع جهاز إلكتروني مزروع"},
    "hard_detail.ulcer_yes": {
        "en": "Recorded: yes. The rule routes the case to a doctor.",
        "ar": "مسجَّل: نعم. تحيل القاعدة الحالة إلى طبيب.",
    },
    "hard_detail.ulcer_no": {"en": "None recorded", "ar": "لم يُسجَّل شيء منها"},
    "hard_detail.unknown": {"en": "Recorded as unknown: not checked yet", "ar": "مسجَّل كغير معروف: لم يُفحص بعد"},
    "hard_detail.not_recorded": {"en": "Not recorded: not checked yet", "ar": "غير مسجَّل: لم يُفحص بعد"},
    "hard_detail.insensate": {
        "en": "Recorded as reduced or absent. The rule is about a rigid device on insensate skin without pressure relief; the orthotist checks each design against it.",
        "ar": "مسجَّل منخفضاً أو غائباً. تخصّ القاعدة جهازاً صلباً على جلد فاقد للإحساس دون تخفيف للضغط؛ ويتحقق أخصائي التقويم من كل تصميم مقابلها.",
    },
    "hard_detail.insensate_options": {
        "en": "Recorded as reduced or absent, and option {ids} lists no lining. The rule is about a rigid device on insensate skin without pressure relief; the orthotist checks whether it applies.",
        "ar": "مسجَّل منخفضاً أو غائباً، والخيار {ids} لا يذكر بطانة. تخصّ القاعدة جهازاً صلباً على جلد فاقد للإحساس دون تخفيف للضغط؛ ويتحقق أخصائي التقويم مما إذا كانت تنطبق.",
    },
    "hard_detail.sensation_intact": {"en": "Recorded as intact", "ar": "مسجَّل سليماً"},
    "hard_detail.contracture": {
        "en": "Recorded: {n}°. The orthotist judges whether the design can accommodate it.",
        "ar": "مسجَّل: {n}°. يقدّر أخصائي التقويم ما إذا كان التصميم يستطيع استيعابه.",
    },
    "hard_detail.implant_yes": {
        "en": "Recorded: yes. A hard stop if FES is chosen.",
        "ar": "مسجَّل: نعم. توقف إلزامي إذا اختير التنبيه الكهربائي.",
    },
    "hard_detail.implant_fes_chosen": {
        "en": "Recorded: yes, and the FES referral is chosen. The rule routes the case to a doctor.",
        "ar": "مسجَّل: نعم، واختيرت إحالة التنبيه الكهربائي. تحيل القاعدة الحالة إلى طبيب.",
    },
    "hard_detail.implant_no": {"en": "Recorded: no", "ar": "مسجَّل: لا"},
    "hard_detail.not_asked": {"en": "Not asked yet", "ar": "لم يُسأل عنه بعد"},
    "hard.option_insensate": {
        "en": "Sensation is recorded as reduced or absent and this option lists no lining. The rule: a rigid device on insensate skin without pressure relief routes the case to a doctor. The orthotist confirms whether it applies.",
        "ar": "الإحساس مسجَّل منخفضاً أو غائباً وهذا الخيار لا يذكر بطانة. القاعدة: الجهاز الصلب على جلد فاقد للإحساس دون تخفيف للضغط يحيل الحالة إلى طبيب. ويؤكد أخصائي التقويم ما إذا كانت تنطبق.",
    },
    "hard_status.clear": {"en": "Clear", "ar": "لا مانع"},
    "hard_status.warn": {"en": "Warning", "ar": "تحذير"},
    "hard_status.judge": {"en": "Orthotist to judge", "ar": "يقدّره أخصائي التقويم"},
    "hard_status.not_checked": {"en": "Not checked yet", "ar": "لم يُفحص بعد"},
    "hard_status.stop": {"en": "Hard stop", "ar": "توقف إلزامي"},
    # Module 1, the analysis page
    "analysis.title": {"en": "Functional case analysis", "ar": "تحليل الحالة الوظيفية"},
    "analysis.conditions": {"en": "Condition module", "ar": "وحدة الحالة المرضية"},
    "analysis.condition_later": {"en": "Later in the roll-out", "ar": "لاحقاً في التوسّع"},
    "analysis.goals": {"en": "Goals, by ICF level", "ar": "الأهداف حسب مستوى التصنيف الدولي للأداء (ICF)"},
    "analysis.exam": {"en": "Structured exam", "ar": "الفحص المنظّم"},
    "analysis.exam_note": {"en": "Every value keeps how it was measured", "ar": "تحتفظ كل قيمة بطريقة قياسها"},
    "analysis.col_measure": {"en": "Measure", "ar": "المقياس"},
    "analysis.col_value": {"en": "Value", "ar": "القيمة"},
    "analysis.col_how": {"en": "How it was measured", "ar": "طريقة القياس"},
    "analysis.col_status": {"en": "Status", "ar": "الحالة"},
    "analysis.recorded": {"en": "Recorded", "ar": "مسجَّل"},
    "analysis.not_asked": {"en": "Not asked", "ar": "لم يُسأل عنه"},
    "analysis.none": {"en": "None", "ar": "لا شيء"},
    "analysis.implant_how": {"en": "Asked only if FES is discussed", "ar": "يُسأل عنه فقط عند مناقشة التنبيه الكهربائي"},
    "analysis.gait": {"en": "Gait, observed phase by phase", "ar": "المشي، ملاحظاً مرحلةً مرحلة"},
    "analysis.gait_note": {
        "en": "Structured checklist · observation only, no sensor data",
        "ar": "قائمة فحص منظّمة · ملاحظة فقط، دون بيانات حساسات",
    },
    "analysis.no_deviation": {"en": "No deviation seen", "ar": "لم يُلاحظ انحراف"},
    "analysis.needed": {"en": "Information needed", "ar": "المعلومات المطلوبة"},
    "analysis.needed_note": {
        "en": "Before design options are shown. Each item shows what the source says about it, in its own words, "
              "with the AI's checked summary when there is one.",
        "ar": "قبل عرض خيارات التصميم. يعرض كل بند ما يقوله المصدر عنه بكلماته، مع ملخص الذكاء الاصطناعي المتحقَّق منه "
              "إن وُجد.",
    },
    "analysis.ai_label": {"en": "AI summary, check it against the quote", "ar": "ملخص بالذكاء الاصطناعي، تحقّق منه مقابل الاقتباس"},
    "analysis.source_passage": {"en": "Source passage", "ar": "مقطع المصدر"},
    "analysis.no_source": {"en": "No source passage found for it.", "ar": "لم يوجد مقطع من المصادر عنه."},
    "analysis.implant_note": {"en": "Needed only if FES is discussed.", "ar": "مطلوب فقط عند مناقشة التنبيه الكهربائي."},
    "analysis.continue": {"en": "Continue to requirements →", "ar": "تابع إلى المتطلبات ←"},
    "analysis.to_review": {"en": "What the sources say, and your review", "ar": "ما تقوله المصادر، ومراجعتك"},
    "analysis.reassess": {"en": "Re-assess: change the intake", "ar": "إعادة التقييم: عدّل استمارة الحالة"},
    "cond.stroke": {"en": "Stroke", "ar": "السكتة الدماغية"},
    "cond.cerebral_palsy": {"en": "Cerebral palsy", "ar": "الشلل الدماغي"},
    "cond.spinal_cord_injury": {"en": "Spinal cord injury", "ar": "إصابة الحبل الشوكي"},
    "cond.peripheral_nerve_injury": {"en": "Peripheral nerve injury", "ar": "إصابة الأعصاب الطرفية"},
    "cond.diabetic_foot": {"en": "Diabetic foot", "ar": "القدم السكرية"},
    "cond.scoliosis": {"en": "Scoliosis", "ar": "الجنف"},
    "icf.participation": {"en": "Participation", "ar": "المشاركة"},
    "icf.activity": {"en": "Activity", "ar": "النشاط"},
    "icf.body_function": {"en": "Body function", "ar": "وظائف الجسم"},
    # The names of the case's values (module 1's exam table, module 2's findings): 'exam_row.' ~ path.
    "exam_row.exam__dorsiflexion_knee_extended_deg": {"en": "Ankle dorsiflexion, knee extended", "ar": "الانثناء الظهري للكاحل، والركبة ممدودة"},
    "exam_row.exam__dorsiflexion_knee_flexed_deg": {"en": "Ankle dorsiflexion, knee flexed", "ar": "الانثناء الظهري للكاحل، والركبة مثنية"},
    "exam_row.exam__plantarflexor_tone_grade": {"en": "Plantarflexor tone", "ar": "توتر العضلات المثنية للأخمص"},
    "exam_row.exam__dorsiflexor_strength": {"en": "Dorsiflexor strength", "ar": "قوة العضلات المثنية الظهرية"},
    "exam_row.exam__knee_extensor_strength": {"en": "Knee extensor strength", "ar": "قوة باسطات الركبة"},
    "exam_row.exam__knee_in_stance": {"en": "Knee in stance", "ar": "الركبة في مرحلة الارتكاز"},
    "exam_row.exam__foot_posture": {"en": "Foot posture", "ar": "وضعية القدم"},
    "exam_row.exam__protective_sensation": {"en": "Plantar protective sensation", "ar": "الإحساس الوقائي في باطن القدم"},
    "exam_row.exam__proprioception": {"en": "Proprioception", "ar": "حس الوضع"},
    "exam_row.exam__skin_condition": {"en": "Skin of foot and calf", "ar": "جلد القدم والساق"},
    "exam_row.exam__ulcer_infection_or_poor_blood_supply": {"en": "Ulcer, infection or poor blood supply", "ar": "قرحة أو عدوى أو ضعف التروية الدموية"},
    "exam_row.walking__gait_speed_m_s": {"en": "Gait speed", "ar": "سرعة المشي"},
    "exam_row.walking__status": {"en": "Walking status", "ar": "حالة المشي"},
    "exam_row.walking__falls_last_6_months": {"en": "Falls in the past 6 months", "ar": "السقطات في الأشهر الستة الماضية"},
    "exam_row.footwear": {"en": "Footwear", "ar": "الحذاء"},
    "exam_row.donning": {"en": "Putting a device on", "ar": "ارتداء الجهاز"},
    "exam_row.prior_orthoses": {"en": "Previous orthoses", "ar": "الأجهزة التقويمية السابقة"},
    "exam_row.implanted_electronic_device": {"en": "Implanted electronic device", "ar": "جهاز إلكتروني مزروع"},
    "exam_row.functional_goals": {"en": "Activity goal", "ar": "هدف النشاط"},
    "exam_row.goal_participation": {"en": "Participation goal", "ar": "هدف المشاركة"},
    "exam_row.goal_body_function": {"en": "Body function goal", "ar": "هدف وظائف الجسم"},
    "exam_row.body_weight_kg": {"en": "Body weight", "ar": "وزن الجسم"},
    # The intake's new fields
    "ort.goals_hint": {
        "en": "Goals by ICF level: participation, activity and body function, in the patient's words.",
        "ar": "الأهداف حسب مستوى التصنيف الدولي للأداء: المشاركة والنشاط ووظائف الجسم، بكلمات المريض.",
    },
    "ort.goal_participation": {"en": "Participation goal (e.g. visit family across town)", "ar": "هدف المشاركة (مثلاً: زيارة الأهل في الطرف الآخر من المدينة)"},
    "ort.goal_body_function": {"en": "Body function goal (e.g. less calf tightness)", "ar": "هدف وظائف الجسم (مثلاً: شدّ أقل في ربلة الساق)"},
    "ort.how_measured": {"en": "How it was measured", "ar": "طريقة القياس"},
    "ort.how_placeholder": {"en": "e.g. goniometer, supine", "ar": "مثلاً: مقياس الزوايا، مستلقياً"},
    "ort.ulcer": {"en": "Ulcer, infection or poor blood supply", "ar": "قرحة أو عدوى أو ضعف التروية الدموية"},
    "ort.ulcer_hint": {
        "en": "The first hard stop of the design's map: \"yes\" routes the case to a doctor.",
        "ar": "أول توقف إلزامي في خريطة التصميم: «نعم» تحيل الحالة إلى طبيب.",
    },
    "ort.implanted_short": {"en": "Implanted electronic device", "ar": "جهاز إلكتروني مزروع"},
    "ort.reassess_heading": {"en": "Re-assess case {id}", "ar": "إعادة تقييم الحالة {id}"},
    "ort.reassess_note": {
        "en": "The case keeps its id and the orthotist's plan; it is analysed again with the values below.",
        "ar": "تحتفظ الحالة بمعرّفها وبخطة أخصائي التقويم؛ وتُحلَّل من جديد بالقيم أدناه.",
    },
    # Module 2
    "req.provisional": {"en": "Provisional until the missing value is recorded", "ar": "مؤقت إلى أن تُسجَّل القيمة الناقصة"},
    "req.conflicts": {"en": "Conflicts", "ar": "التعارضات"},
    "req.no_conflicts": {
        "en": "No conflict noted. When two requirements pull against each other, note it here.",
        "ar": "لم يُسجَّل تعارض. إذا تعارض متطلبان فسجّل ذلك هنا.",
    },
    "req.against": {"en": "{first} against {second}.", "ar": "{first} مقابل {second}."},
    "req.note_conflict": {"en": "Note a conflict", "ar": "سجّل تعارضاً"},
    "req.conflict_first": {"en": "Requirement", "ar": "المتطلب"},
    "req.conflict_second": {"en": "against", "ar": "مقابل"},
    "req.conflict_note": {"en": "Note (the orthotist's words)", "ar": "ملاحظة (بكلمات أخصائي التقويم)"},
    "req.save_conflicts": {"en": "Save the conflicts", "ar": "احفظ التعارضات"},
    "req.graph": {
        "en": "The design knowledge graph links each requirement to the parts that address it (module 3) and to what "
              "the sources say about them.",
        "ar": "تربط شبكة معرفة التصميم كل متطلب بالمكونات التي تلبّيه (الوحدة 3) وبما تقوله المصادر عنها.",
    },
    "req_group.missing": {"en": "Not recorded yet (the requirement is then provisional)", "ar": "لم يُسجَّل بعد (فيكون المتطلب مؤقتاً)"},
    # Module 3
    "options.summary": {"en": "Under the device's name (e.g. stop set at the calf length)", "ar": "تحت اسم الجهاز (مثلاً: المانع مضبوط على طول الساق)"},
    "options.mark_note": {"en": "Mark's word (e.g. adjustable)", "ar": "وصف التقدير (مثلاً: قابل للتعديل)"},
    "options.costs": {"en": "Costs the patient", "ar": "ما يكلّفه للمريض"},
    "options.evidence": {"en": "Evidence", "ar": "الأدلة"},
    "options.no_outcome_evidence": {"en": "practice, no outcome evidence", "ar": "ممارسة، بلا دليل على النتائج"},
    "options.parts_for_case": {"en": "Materials and parts for this case", "ar": "المواد والمكونات لهذه الحالة"},
    "options.part_note": {"en": "Note (e.g. thickness by body weight, a practice rule)", "ar": "ملاحظة (مثلاً: السماكة حسب وزن الجسم، قاعدة ممارسة)"},
    "options.part_sources": {"en": "What the library says about it ({n})", "ar": "ما تقوله المكتبة عنه ({n})"},
    "options.stock": {"en": "Clinic stock", "ar": "مخزون العيادة"},
    "options.checks": {"en": "Check at fitting", "ar": "ما يُفحص عند التركيب"},
    "options.other_notes": {"en": "Other notes", "ar": "ملاحظات أخرى"},
    "options.choose_option": {"en": "Choose option {id}", "ar": "اختر الخيار {id}"},
    "options.chosen_by": {"en": "Chosen by the orthotist", "ar": "اختاره أخصائي التقويم"},
    "options.fes_kicker": {"en": "To discuss with the rehabilitation team", "ar": "للنقاش مع فريق التأهيل"},
    "options.fes_title": {"en": "FES, peroneal nerve stimulation", "ar": "التنبيه الكهربائي الوظيفي للعصب الشظوي"},
    "options.check_first": {"en": "Check first:", "ar": "يُفحص أولاً:"},
    "options.choose_referral": {"en": "Choose referral", "ar": "اختر الإحالة"},
    "options.referral_chosen": {"en": "Referral chosen", "ar": "اختيرت الإحالة"},
    "options.fes_chosen": {"en": "Referral to discuss FES", "ar": "إحالة لمناقشة التنبيه الكهربائي"},
    "options.not_chosen": {"en": "Not chosen yet", "ar": "لم يُختر بعد"},
    "options.record_and_design": {"en": "Record and go to design →", "ar": "سجّل وانتقل إلى التصميم ←"},
    "options.fes_edit": {"en": "Write or change the FES referral's checks", "ar": "اكتب فحوص إحالة التنبيه الكهربائي أو عدّلها"},
    "options.fes_checks": {"en": "Check first (the orthotist's words)", "ar": "يُفحص أولاً (بكلمات أخصائي التقويم)"},
    "options.fes_note": {"en": "Note", "ar": "ملاحظة"},
    "options.fes_save": {"en": "Save the referral", "ar": "احفظ الإحالة"},
    # Module 4
    "design.fes_chosen": {
        "en": "The referral to discuss FES was chosen: no orthosis to design.",
        "ar": "اختيرت إحالة لمناقشة التنبيه الكهربائي: لا جهاز تقويم لتصميمه.",
    },
    "design.n_to_approve": {"en": "{n} to approve", "ar": "بانتظار الاعتماد: {n}"},
    "design.viewer": {"en": "Viewer", "ar": "العارض"},
    "design.view_side": {"en": "Side", "ar": "جانبي"},
    "design.view_spots": {"en": "Pressure hot spots", "ar": "نقاط الضغط"},
    "design.view_compare": {"en": "Compare with the previous version", "ar": "قارن بالنسخة السابقة"},
    "design.schematic_label": {"en": "Side view of a {device}, schematic", "ar": "منظر جانبي تخطيطي: {device}"},
    "design.schematic_note": {
        "en": "Schematic of the device type, not this patient's scan: the scan stays in the CAD tool.",
        "ar": "رسم تخطيطي لنوع الجهاز، وليس مسح هذا المريض: يبقى المسح في أداة التصميم.",
    },
    "design.capture_note": {"en": "Capture:", "ar": "أخذ الشكل:"},
    "design.no_hot_spots": {"en": "No hot spots entered.", "ar": "لم تُدخل نقاط ضغط."},
    "design.same_values": {"en": "Same values.", "ar": "القيم نفسها."},
    "design.nothing_to_compare": {"en": "One version so far: nothing to compare.", "ar": "نسخة واحدة حتى الآن: لا شيء للمقارنة."},
    "design.simulation": {"en": "Simulation", "ar": "المحاكاة"},
    "design.simulation_badge": {"en": "As entered from the CAD tool · confirm at fitting", "ar": "كما أُدخلت من أداة التصميم · تُؤكَّد عند التركيب"},
    "design.no_simulation": {
        "en": "No simulation results entered: the app runs no simulation.",
        "ar": "لم تُدخل نتائج محاكاة: لا يجري التطبيق أي محاكاة.",
    },
    "design.hot_spots": {"en": "Pressure hot spots", "ar": "نقاط الضغط"},
    "design.relief_note": {"en": "Relief (e.g. added at all three in v3)", "ar": "تخفيف الضغط (مثلاً: أُضيف عند الثلاث في النسخة 3)"},
    "design.simulation_edit": {"en": "Enter the simulation results", "ar": "أدخل نتائج المحاكاة"},
    "design.sim_item": {"en": "What was simulated", "ar": "ما الذي حوكي"},
    "design.sim_result": {"en": "Result", "ar": "النتيجة"},
    "design.save_simulation": {"en": "Save the simulation", "ar": "احفظ المحاكاة"},
    "design.steps_edit": {"en": "Update the steps", "ar": "حدّث الخطوات"},
    "design.approved": {"en": "Approved", "ar": "معتمد"},
    "design.to_approve": {"en": "To approve", "ar": "بانتظار الاعتماد"},
    "design.approve": {"en": "Approve", "ar": "اعتمد"},
    "design.parameters_edit": {"en": "Change the parameters (saves a new version)", "ar": "عدّل المعايير (يحفظ نسخة جديدة)"},
    "design.value": {"en": "Value", "ar": "القيمة"},
    "design.basis": {"en": "Basis", "ar": "الأساس"},
    "design.basis_unset": {"en": "Not recorded", "ar": "غير مسجَّل"},
    "design.basis_note": {"en": "Basis note (e.g. thickness by body weight)", "ar": "ملاحظة الأساس (مثلاً: السماكة حسب وزن الجسم)"},
    "design.by": {"en": "Saved by (e.g. orthotist)", "ar": "حفظها (مثلاً: أخصائي التقويم)"},
    "design.sent": {"en": "Sent to manufacture: {at}", "ar": "أُرسل إلى التصنيع: {at}"},
    "design.send": {"en": "Send to manufacture", "ar": "أرسل إلى التصنيع"},
    "design.send_note": {"en": "Every parameter must be approved first.", "ar": "يجب اعتماد كل معيار أولاً."},
    "design.export_sheet": {"en": "Export the fabrication sheet", "ar": "صدّر ورقة التصنيع"},
    "design.to_fit": {"en": "Go to fit and tune →", "ar": "انتقل إلى التركيب والضبط ←"},
    "basis.orthotist": {"en": "Set by the orthotist", "ar": "حدده أخصائي التقويم"},
    "basis.practice_rule": {"en": "Practice rule", "ar": "قاعدة ممارسة"},
    "basis.scan": {"en": "From the scan", "ar": "من المسح"},
    "step.simulate": {"en": "Simulate", "ar": "المحاكاة"},
    "method.fea": {"en": "Simulation in the CAD tool", "ar": "محاكاة في أداة التصميم"},
    "param.joint_axis": {"en": "Joint axis", "ar": "محور المفصل"},
    "sheet.title": {"en": "Fabrication sheet", "ar": "ورقة التصنيع"},
    "sheet.not_approved": {"en": "Not every parameter is approved yet.", "ar": "لم تُعتمد كل المعايير بعد."},
    # Module 5
    "fit.title": {"en": "Fit, tune and train", "ar": "التركيب والضبط والتدريب"},
    "fit.checkout": {"en": "Check-out", "ar": "الفحص عند التسليم"},
    "fit.checkout_start": {
        "en": "Starting from the chosen option's checks at fitting and the requirements: tick, change or add.",
        "ar": "بدءاً بما يُفحص عند التركيب في الخيار المختار وبالمتطلبات: علّم أو عدّل أو أضف.",
    },
    "fit.done": {"en": "Done", "ar": "تم"},
    "fit.check_item": {"en": "What is checked", "ar": "ما يُفحص"},
    "fit.check_note": {"en": "Note (e.g. needs practice)", "ar": "ملاحظة (مثلاً: يحتاج إلى تمرين)"},
    "fit.save_checkout": {"en": "Save the check-out", "ar": "احفظ الفحص عند التسليم"},
    "fit.tuning": {"en": "Tuning", "ar": "الضبط"},
    "fit.tuning_note": {"en": "Observed by the orthotist", "ar": "كما لاحظه أخصائي التقويم"},
    "fit.tune_step": {"en": "Step", "ar": "الخطوة"},
    "fit.tune_change": {"en": "Change", "ar": "التغيير"},
    "fit.tune_seen": {"en": "What the orthotist saw", "ar": "ما لاحظه أخصائي التقويم"},
    "fit.tuning_edit": {"en": "Add or change tuning steps", "ar": "أضف خطوات الضبط أو عدّلها"},
    "fit.save_tuning": {"en": "Save the tuning", "ar": "احفظ الضبط"},
    "fit.before_after": {"en": "Before and after", "ar": "قبل وبعد"},
    "fit.measures": {"en": "Before and after", "ar": "قبل وبعد"},
    "fit.before_after_note": {
        "en": "Entered by the clinician · observation only, no video analysed",
        "ar": "يُدخلها المختص · ملاحظة فقط، دون تحليل فيديو",
    },
    "fit.measures_start": {
        "en": "Starting from the intake's gait speed and deviations: write what was seen after.",
        "ar": "بدءاً بسرعة المشي والانحرافات المسجّلة في استمارة الحالة: اكتب ما لوحظ بعد ذلك.",
    },
    "fit.ba_measure": {"en": "Measure", "ar": "المقياس"},
    "fit.ba_before": {"en": "Before", "ar": "قبل"},
    "fit.ba_after": {"en": "After", "ar": "بعد"},
    "fit.ba_note": {"en": "Note", "ar": "ملاحظة"},
    "fit.measures_edit": {"en": "Enter before and after", "ar": "أدخل قبل وبعد"},
    "fit.save_measures": {"en": "Save before and after", "ar": "احفظ قبل وبعد"},
    "fit.gait_speed": {"en": "Gait speed", "ar": "سرعة المشي"},
    "fit.present": {"en": "present", "ar": "موجود"},
    "fit.delivered_on": {"en": "Delivered on", "ar": "تاريخ التسليم"},
    "fit.save_delivered": {"en": "Save the date", "ar": "احفظ التاريخ"},
    "fit.training": {"en": "Training plan", "ar": "خطة التدريب"},
    "fit.set_by": {"en": "Set by {who}", "ar": "حددها: {who}"},
    "fit.wearing": {"en": "Wearing time", "ar": "مدة الارتداء"},
    "fit.practice": {"en": "Practice with the orthosis", "ar": "التمرين مع الجهاز"},
    "fit.no_training": {"en": "No training plan entered yet.", "ar": "لم تُدخل خطة تدريب بعد."},
    "fit.training_edit": {"en": "Enter the training plan", "ar": "أدخل خطة التدريب"},
    "fit.training_by": {"en": "Set by (e.g. physiotherapist)", "ar": "حددها (مثلاً: أخصائي العلاج الطبيعي)"},
    "fit.save_training": {"en": "Save the training plan", "ar": "احفظ خطة التدريب"},
    "fit.leaflet": {"en": "Patient leaflet", "ar": "نشرة المريض"},
    "fit.leaflet_language": {"en": "Leaflet language", "ar": "لغة النشرة"},
    "fit.leaflet_empty": {"en": "Not written yet in this language.", "ar": "لم تُكتب بعد بهذه اللغة."},
    "fit.no_leaflet": {
        "en": "No leaflet written yet: the orthotist writes it, in Arabic and English.",
        "ar": "لم تُكتب نشرة بعد: يكتبها أخصائي التقويم بالعربية والإنجليزية.",
    },
    "fit.leaflet_check": {
        "en": "The Arabic text is checked by an Arabic-reading orthotist before any patient sees it.",
        "ar": "يراجع النصَّ العربي أخصائيُّ تقويم يقرأ العربية قبل أن يراه أي مريض.",
    },
    "fit.checked_by_who": {"en": "Checked by: {who}.", "ar": "راجعه: {who}."},
    "fit.print_leaflet": {"en": "Print the leaflet", "ar": "اطبع النشرة"},
    "fit.leaflet_edit": {"en": "Write or change the leaflet", "ar": "اكتب النشرة أو عدّلها"},
    "fit.leaflet_ar": {"en": "Arabic text", "ar": "النص العربي"},
    "fit.leaflet_en": {"en": "English text", "ar": "النص الإنجليزي"},
    "fit.checked_by": {"en": "Arabic text checked by", "ar": "راجع النصَّ العربي"},
    "fit.save_leaflet": {"en": "Save the leaflet", "ar": "احفظ النشرة"},
    "fit.to_follow_up": {"en": "Set up follow-up →", "ar": "أعدّ المتابعة ←"},
    "leaflet.next_review": {"en": "Next review", "ar": "موعد المراجعة القادم"},
    # Module 6
    "fu.title": {"en": "Follow-up", "ar": "المتابعة"},
    "fu.visits": {"en": "Visits", "ar": "الزيارات"},
    "fu.measures": {"en": "Outcome measures", "ar": "مقاييس النتائج"},
    "fu.measures_note": {"en": "Entered by the clinician at each visit", "ar": "يُدخلها المختص في كل زيارة"},
    "fu.no_values": {"en": "No value entered yet.", "ar": "لم تُدخل قيمة بعد."},
    "fu.no_measures": {"en": "No outcome measure set up yet.", "ar": "لم يُعدّ مقياس نتائج بعد."},
    "fu.due_next": {"en": "Due at the next review", "ar": "المطلوب في المراجعة القادمة"},
    "fu.as_recorded": {
        "en": "Values are shown as recorded; the clinician judges the change.",
        "ar": "تُعرض القيم كما سُجّلت؛ ويقدّر المختص التغيّر.",
    },
    "fu.measures_edit": {"en": "Set up the outcome measures", "ar": "أعدّ مقاييس النتائج"},
    "fu.measure_name": {"en": "Measure", "ar": "المقياس"},
    "fu.measure_unit": {"en": "Unit", "ar": "الوحدة"},
    "fu.measure_how": {"en": "How it is measured", "ar": "طريقة القياس"},
    "fu.save_measures": {"en": "Save the measures", "ar": "احفظ المقاييس"},
    "fu.visits_edit": {"en": "Add or change visits, with the values entered at each", "ar": "أضف الزيارات أو عدّلها، مع القيم المدخلة في كل منها"},
    "fu.visit_n": {"en": "Visit {n}", "ar": "الزيارة {n}"},
    "fu.visit": {"en": "Visit", "ar": "الزيارة"},
    "fu.date": {"en": "Date", "ar": "التاريخ"},
    "fu.status": {"en": "Status", "ar": "الحالة"},
    "fu.value": {"en": "Value", "ar": "القيمة"},
    "fu.wearing": {"en": "Wearing time, patient report", "ar": "مدة الارتداء، حسب المريض"},
    "fu.puts_on_alone": {"en": "Puts it on alone", "ar": "يرتديه وحده"},
    "fu.device_condition": {"en": "Device condition", "ar": "حالة الجهاز"},
    "fu.notes": {"en": "Notes", "ar": "ملاحظات"},
    "fu.visits_note": {
        "en": "A visit needs its name; empty a row to remove it.",
        "ar": "تحتاج الزيارة إلى اسمها؛ أفرغ الصف لحذفها.",
    },
    "fu.save_visits": {"en": "Save the visits", "ar": "احفظ الزيارات"},
    "fu.alerts": {"en": "Alerts", "ar": "التنبيهات"},
    "fu.review_due": {"en": "{visit} due {date}.", "ar": "{visit} مستحقة في {date}."},
    "fu.no_date": {"en": "no date set", "ar": "دون تاريخ"},
    "fu.due_with": {"en": "Book with it: {what}.", "ar": "احجز معها: {what}."},
    "fu.no_alerts": {"en": "No alerts.", "ar": "لا تنبيهات."},
    "fu.back_to.fit": {"en": "Adjust in fit and tune →", "ar": "عدّل في التركيب والضبط ←"},
    "fu.back_to.options": {"en": "Redesign in the options →", "ar": "أعد التصميم في الخيارات ←"},
    "fu.back_to.analysis": {"en": "Re-assess in the case analysis →", "ar": "أعد التقييم في تحليل الحالة ←"},
    "fu.alerts_edit": {"en": "Add or change alerts", "ar": "أضف التنبيهات أو عدّلها"},
    "fu.alert_text": {"en": "Alert (the clinician's words)", "ar": "التنبيه (بكلمات المختص)"},
    "fu.alert_back_to": {"en": "Loops back to", "ar": "يعود إلى"},
    "fu.resolved": {"en": "Resolved", "ar": "حُلّ"},
    "fu.save_alerts": {"en": "Save the alerts", "ar": "احفظ التنبيهات"},
    "fu.wearing_heading": {"en": "Wearing and device", "ar": "الارتداء والجهاز"},
    "fu.from_visit": {"en": "As entered at: {visit}", "ar": "كما أُدخل في: {visit}"},
    "fu.no_done_visit": {"en": "No visit marked done yet.", "ar": "لم تُعلَّم زيارة منجزة بعد."},
    "fu.loop_back": {"en": "Loop back", "ar": "العودة"},
    "fu.retune": {"en": "Re-tune", "ar": "إعادة الضبط"},
    "fu.redesign": {"en": "Redesign", "ar": "إعادة التصميم"},
    "fu.reassess": {"en": "Re-assess", "ar": "إعادة التقييم"},
    "fu.summary": {"en": "Summary for the physiotherapist", "ar": "ملخص لأخصائي العلاج الطبيعي"},
    "visit_status.done": {"en": "done", "ar": "منجزة"},
    "visit_status.due": {"en": "due", "ar": "مستحقة"},
    "visit_status.not_booked": {"en": "not booked", "ar": "غير محجوزة"},
    "summary.title": {"en": "Summary for the physiotherapist", "ar": "ملخص لأخصائي العلاج الطبيعي"},
    "print.note": {"en": "Print this page from the browser (Ctrl+P).", "ar": "اطبع هذه الصفحة من المتصفح (Ctrl+P)."},
    "print.back": {"en": "Back", "ar": "رجوع"},
    "print.not_checked": {
        "en": "The Arabic text has not been checked by an Arabic-reading orthotist yet: don't give it to a patient.",
        "ar": "لم يراجع النصَّ العربي أخصائيُّ تقويم يقرأ العربية بعد: لا تعطه لمريض.",
    },
    "review.ort_kicker": {"en": "What the sources say, and your review", "ar": "ما تقوله المصادر، ومراجعتك"},
    "review.to_analysis": {"en": "← Module 1: the case analysis", "ar": "→ الوحدة 1: تحليل الحالة"},
    "error.too_many_lines": {"en": "{field}: at most {n} lines.", "ar": "{field}: {n} أسطر على الأكثر."},
    "error.too_many_rows": {"en": "{field}: at most {n} rows.", "ar": "{field}: {n} صفوف على الأكثر."},
    "error.date": {"en": "{field}: enter a date.", "ar": "{field}: أدخل تاريخاً."},
    "error.conflict_incomplete": {"en": "A conflict needs two requirements and a note.", "ar": "يحتاج التعارض إلى متطلبين وملاحظة."},
    "error.approve_first": {
        "en": "Every parameter must be approved before sending to manufacture.",
        "ar": "يجب اعتماد كل معيار قبل الإرسال إلى التصنيع.",
    },
    "error.visit_needs_name": {"en": "A visit with values needs its name.", "ar": "تحتاج الزيارة ذات القيم إلى اسمها."},
    "error.measure_needs_name": {"en": "A measure needs its name.", "ar": "يحتاج المقياس إلى اسمه."},
    "error.alert_needs_text": {"en": "An alert needs its text.", "ar": "يحتاج التنبيه إلى نصه."},
    # ---- Every page's header and the prosthetics map (2026-10-23; shared/templates/ui_header.html) ----
    "domain.prosthetics": {"en": "Prosthetics", "ar": "الأطراف الاصطناعية"},
    "domain.orthotics": {"en": "Orthotics", "ar": "تقويم العظام"},
    "domain.switch": {"en": "Domains", "ar": "المجالات"},
    "domain.modules": {"en": "{domain} modules", "ar": "وحدات {domain}"},
    # ---- The prosthetic module pages (plan Part 3, 2026-10-24; prosthetics/modules.py, hard_stops.py) ----
    "pmod.side": {"en": "{side} side", "ar": "الجانب: {side}"},
    "pmod.k_level": {"en": "recorded {k}", "ar": "المسجَّل {k}"},
    "pmod.months": {"en": "{n} months since amputation", "ar": "الأشهر منذ البتر: {n}"},
    "pmod.assess": {"en": "1 Assess", "ar": "1 التقييم"},
    "pmod.components": {"en": "2–3 Requirements & components", "ar": "2–3 المتطلبات والمكونات"},
    "pmod.fitting": {"en": "4 Design & fitting", "ar": "4 التصميم والتركيب"},
    "pmod.follow_up": {"en": "5 Follow-up", "ar": "5 المتابعة"},
    "pmod.prosthetist_decides": {
        "en": "Decision support: the prosthetist decides",
        "ar": "دعم القرار: أخصائي الأطراف الاصطناعية هو من يقرر",
    },
    "pmod.modules_2_3": {"en": "Modules 2–3", "ar": "الوحدتان 2–3"},
    "pmod.to_assess": {"en": "← Module 1: the assessment", "ar": "→ الوحدة 1: التقييم"},
    "pmod.to_components": {
        "en": "Modules 2–3: requirements and components →",
        "ar": "الوحدتان 2–3: المتطلبات والمكونات ←",
    },
    "pmod.needs_case": {"en": "Open a prosthetic case first", "ar": "افتح حالة طرف اصطناعي أولاً"},
    "pmod.mark_on_review": {"en": "Mark them on the review page →", "ar": "قدّرها في صفحة المراجعة ←"},
    "pmod.no_statements": {
        "en": "Nothing from the sources for this here; the review page shows the passages the search found.",
        "ar": "لا شيء من المصادر عن هذا هنا؛ وتعرض صفحة المراجعة المقاطع التي وجدها البحث.",
    },
    "pmod.none_reported": {"en": "asked, none", "ar": "سُئل عنه، لا شيء"},
    "pmap.title": {"en": "Prosthetics: the modules", "ar": "الأطراف الاصطناعية: الوحدات"},
    "pmap.intro": {
        "en": "From the amputation case to follow-up, in four modules. Every value on them is the prosthetist's; the review page shows what the sources say for each case and takes the specialist's marks.",
        "ar": "من حالة البتر إلى المتابعة، في أربع وحدات. كل قيمة فيها لأخصائي الأطراف الاصطناعية؛ وتعرض صفحة المراجعة ما تقوله المصادر عن كل حالة وتأخذ تقديرات المختص.",
    },
    "pmap.new_case": {"en": "New prosthetic case", "ar": "حالة طرف اصطناعي جديدة"},
    "pmap.from_case": {
        "en": "Opens from a case: the header's tabs lead to it.",
        "ar": "تُفتح من حالة: تؤدي إليها علامات التبويب في الشريط العلوي.",
    },
    "pmap.latest_case": {"en": "Open for the latest case", "ar": "افتح لآخر حالة"},
    "pmap.principle": {
        "en": "The tool shows the case and what the sources say, each AI summary over a quote checked word for word: it never diagnoses, chooses or ranks components, or judges readiness for fitting.",
        "ar": "تعرض الأداة الحالة وما تقوله المصادر، وكل ملخص من الذكاء الاصطناعي فوق اقتباس يُتحقق منه كلمةً كلمة: لا تشخّص ولا تختار المكونات ولا ترتّبها ولا تحكم على الجاهزية للتركيب.",
    },
    "pmap_name.assess": {"en": "Amputation case assessment", "ar": "تقييم حالة البتر"},
    "pmap_name.components": {"en": "Requirements and component support", "ar": "المتطلبات ودعم اختيار المكونات"},
    "pmap_name.fitting": {"en": "Design and fitting decisions", "ar": "قرارات التصميم والتركيب"},
    "pmap_name.follow_up": {"en": "Follow-up and evaluation", "ar": "المتابعة والتقييم"},
    "pmap_does.assess": {
        "en": "The case as measured, each value with how it was measured; mobility measured and the K-level the prosthetist set; goals by ICF level; the information still needed, with what the sources say about why (use case 01); the draft hard-stop checks.",
        "ar": "الحالة كما قيست، وكل قيمة مع طريقة قياسها؛ والتنقل كما قيس والمستوى الوظيفي الذي حدّده أخصائي الأطراف الاصطناعية؛ والأهداف حسب مستوى ICF؛ والمعلومات التي ما زالت مطلوبة مع ما تقوله المصادر عن سببها (حالة الاستخدام 01)؛ وفحوص التوقف الإلزامي المسوّدة.",
    },
    "pmap_does.components": {
        "en": "What the prosthesis must do, then up to three options per component, typed by the prosthetist and shown side by side, never ranked, next to what the sources say (use case 02); the prosthetist's configuration and reason are logged.",
        "ar": "ما يجب أن يؤديه الطرف الاصطناعي، ثم حتى ثلاثة خيارات لكل مكوّن يكتبها أخصائي الأطراف الاصطناعية وتُعرض جنباً إلى جنب دون ترتيب، بجانب ما تقوله المصادر (حالة الاستخدام 02)؛ وتُسجَّل تشكيلة الأخصائي وسببها.",
    },
    "pmap_does.fitting": {
        "en": "The six fitting steps, an observation log next to the possible causes in the sources' words, check-socket versions, what bears on a definitive prosthesis, the alignment record and the fabrication sheet.",
        "ar": "خطوات التركيب الست، وسجل الملاحظات بجانب الأسباب المحتملة بكلمات المصادر، وإصدارات التجويف التجريبي، وما يتعلق بالطرف النهائي، وسجل المحاذاة، وورقة التصنيع.",
    },
    "pmap_does.follow_up": {
        "en": "Visits, outcome measures as recorded at each, alerts in the clinician's words and links back to refit, review the components or re-assess.",
        "ar": "الزيارات، ومقاييس النتائج كما سُجّلت في كل منها، والتنبيهات بكلمات المختص، وروابط العودة لإعادة التركيب أو مراجعة المكونات أو إعادة التقييم.",
    },
    "hard.open_wound": {"en": "Open wound or infection", "ar": "جرح مفتوح أو عدوى"},
    "hard.volume_changing": {"en": "Changing volume", "ar": "حجم متغيّر"},
    "hard.neuropathic_foot": {"en": "Neuropathic other foot", "ar": "اعتلال أعصاب في القدم الأخرى"},
    "hard_rule.open_wound": {"en": "Open wound or infection", "ar": "جرح مفتوح أو عدوى"},
    "hard_rule.volume_changing": {
        "en": "Changing volume: a definitive socket waits for stable volume; the prosthetist decides when",
        "ar": "حجم متغيّر: ينتظر التجويف النهائي استقرار الحجم؛ ويقرر أخصائي الأطراف الاصطناعية متى",
    },
    "hard_rule.neuropathic_foot": {
        "en": "Neuropathic other foot: referral to the diabetic foot team, if not under its care",
        "ar": "اعتلال أعصاب في القدم الأخرى: إحالة إلى فريق القدم السكرية إن لم تكن تحت رعايته",
    },
    "hard_detail.wound_open": {
        "en": "Recorded: the wound is open. The draft rule matches what was recorded.",
        "ar": "مسجَّل: الجرح مفتوح. تنطبق القاعدة المسوّدة على ما سُجِّل.",
    },
    "hard_detail.infection_yes": {
        "en": "Recorded: signs of infection. The draft rule matches what was recorded.",
        "ar": "مسجَّل: علامات عدوى. تنطبق القاعدة المسوّدة على ما سُجِّل.",
    },
    "hard_detail.wound_healing": {
        "en": "Recorded: the wound is healing. The prosthetist judges whether the rule applies.",
        "ar": "مسجَّل: الجرح قيد الالتئام. يقدّر أخصائي الأطراف الاصطناعية ما إذا كانت القاعدة تنطبق.",
    },
    "hard_detail.wound_healed_no_infection": {
        "en": "Recorded: the wound is healed, no signs of infection",
        "ar": "مسجَّل: الجرح ملتئم، ولا علامات عدوى",
    },
    "hard_detail.infection_not_recorded": {
        "en": "The wound is recorded as healed; signs of infection are not recorded yet (module 1): not checked yet",
        "ar": "الجرح مسجَّل ملتئماً؛ ولم تُسجَّل علامات العدوى بعد (الوحدة 1): لم يُفحص بعد",
    },
    "hard_detail.volume_fluctuating": {
        "en": "Recorded as fluctuating. The rule: a definitive socket waits for stable volume; the prosthetist decides when.",
        "ar": "مسجَّل متذبذباً. القاعدة: ينتظر التجويف النهائي استقرار الحجم؛ ويقرر أخصائي الأطراف الاصطناعية متى.",
    },
    "hard_detail.volume_stable": {"en": "Recorded as stable", "ar": "مسجَّل مستقراً"},
    "hard_detail.neuropathy_no": {"en": "Recorded: no neuropathy", "ar": "مسجَّل: لا اعتلال أعصاب"},
    "hard_detail.team_care": {
        "en": "Recorded: neuropathy, under the diabetic foot team's care",
        "ar": "مسجَّل: اعتلال أعصاب، تحت رعاية فريق القدم السكرية",
    },
    "hard_detail.team_refer": {
        "en": "Recorded: neuropathy, not under the diabetic foot team's care. The rule refers the case to the diabetic foot team.",
        "ar": "مسجَّل: اعتلال أعصاب، وليست تحت رعاية فريق القدم السكرية. تحيل القاعدة الحالة إلى فريق القدم السكرية.",
    },
    "hard_detail.team_unknown": {
        "en": "Recorded: neuropathy. Is the diabetic foot team aware? Whether it cares for the foot is not recorded.",
        "ar": "مسجَّل: اعتلال أعصاب. هل فريق القدم السكرية على علم؟ لم يُسجَّل ما إذا كانت القدم تحت رعايته.",
    },
    "phard.judge": {"en": "Prosthetist to judge", "ar": "يقدّره أخصائي الأطراف الاصطناعية"},
    "phard.stop_banner": {
        "en": "A hard-stop rule matches what was recorded; the rule routes the case to the person it names:",
        "ar": "تنطبق على ما سُجِّل قاعدة توقف إلزامي، وهي تحيل الحالة إلى الشخص الذي تسمّيه:",
    },
    "phard.draft_rules": {
        "en": "Draft rules from the design, awaiting the owner's approval: they are not the clinic's rules yet. The tool only looks up what was recorded and never infers a value; the prosthetist decides, with the person a rule routes the case to.",
        "ar": "قواعد مسوّدة من التصميم، بانتظار موافقة المالك: ليست قواعد العيادة بعد. تكتفي الأداة بالنظر فيما سُجِّل ولا تستنتج أي قيمة؛ والقرار لأخصائي الأطراف الاصطناعية، مع الشخص الذي تحيل إليه القاعدة الحالة.",
    },
    "passess.title": {"en": "Amputation case assessment", "ar": "تقييم حالة البتر"},
    "passess.intro": {
        "en": "Every value keeps how it was measured. Mobility is measured, never inferred from age or cause.",
        "ar": "تحتفظ كل قيمة بطريقة قياسها. يُقاس التنقل ولا يُستنتج من العمر أو السبب.",
    },
    "passess.body": {"en": "Residual limb and body", "ar": "الطرف المتبقي والجسم"},
    "passess.body_note": {"en": "Recorded by the prosthetist", "ar": "يسجّلها أخصائي الأطراف الاصطناعية"},
    "passess.mobility": {"en": "Mobility, measured", "ar": "التنقل كما قيس"},
    "passess.k_level": {"en": "Functional level", "ar": "المستوى الوظيفي"},
    "passess.k_set_by": {"en": "Set by the prosthetist", "ar": "يحدّده أخصائي الأطراف الاصطناعية"},
    "passess.no_mobility": {"en": "No mobility measure recorded yet.", "ar": "لم يُسجَّل مقياس للتنقل بعد."},
    "passess.k_note": {
        "en": "The level's definition is shown in the source's own words, with its page. The system never assigns a K-level.",
        "ar": "يُعرض تعريف المستوى بكلمات المصدر مع صفحته. لا يحدّد النظام المستوى الوظيفي أبداً.",
    },
    "passess.k_sources": {
        "en": "What the sources say about functional levels",
        "ar": "ما تقوله المصادر عن المستويات الوظيفية",
    },
    "passess.record": {"en": "Record the rest of the assessment", "ar": "سجّل بقية التقييم"},
    "passess.record_note": {
        "en": "The intake form's values stay as entered there. Here: how each value was measured, and the values the intake form doesn't ask.",
        "ar": "تبقى قيم استمارة الحالة كما أُدخلت هناك. وهنا: طريقة قياس كل قيمة، والقيم التي لا تسأل عنها الاستمارة.",
    },
    "passess.from_intake": {"en": "From the intake form", "ar": "من استمارة الحالة"},
    "passess.not_asked_option": {"en": "Not asked", "ar": "لم يُسأل عنه"},
    "passess.test": {"en": "Test, as named", "ar": "الاختبار، باسمه"},
    "passess.result": {"en": "Result", "ar": "النتيجة"},
    "passess.test_how": {"en": "How it was done", "ar": "كيف أُجري"},
    "passess.mobility_note": {
        "en": "Measured with (e.g. the preparatory prosthesis)",
        "ar": "قيس مع (مثلاً الطرف المؤقت)",
    },
    "passess.k_at_intake": {
        "en": "The functional level (K-level) is set by the prosthetist on the intake form.",
        "ar": "يحدّد أخصائي الأطراف الاصطناعية المستوى الوظيفي (K) في استمارة الحالة.",
    },
    "passess.save": {"en": "Save the assessment", "ar": "احفظ التقييم"},
    "passess.needed_note": {
        "en": "Before component options are shown. Each item shows what the source says about it, in its own words, with the AI's checked summary when there is one.",
        "ar": "قبل عرض خيارات المكونات. يعرض كل بند ما يقوله المصدر عنه بكلماته، مع ملخص الذكاء الاصطناعي المتحقَّق منه إن وُجد.",
    },
    "passess.asked_here": {
        "en": "Recorded on this page, under the assessment.",
        "ar": "يُسجَّل في هذه الصفحة ضمن التقييم.",
    },
    "passess.continue": {"en": "Continue to requirements →", "ar": "تابع إلى المتطلبات ←"},
    "passess.how": {"en": "How it was measured", "ar": "طريقة القياس"},
    "passess.joint_range": {"en": "Joint range", "ar": "مدى حركة المفاصل"},
    "passess.strength": {"en": "Strength", "ar": "القوة العضلية"},
    "passess.goal_participation": {"en": "Participation goal", "ar": "هدف المشاركة"},
    "passess.goal_body_function": {"en": "Body function goal", "ar": "هدف وظائف الجسم"},
    "passess.home_work_setting": {"en": "Home and work setting", "ar": "بيئة المنزل والعمل"},
    "prow.residual_limb__wound_status": {"en": "Wound", "ar": "الجرح"},
    "prow.assessment__infection": {"en": "Signs of infection", "ar": "علامات العدوى"},
    "prow.residual_limb__volume_stability": {"en": "Volume", "ar": "الحجم"},
    "prow.residual_limb__length_description": {"en": "Length and shape", "ar": "الطول والشكل"},
    "prow.residual_limb__skin_condition": {"en": "Skin", "ar": "الجلد"},
    "prow.residual_limb__pain": {"en": "Pain", "ar": "الألم"},
    "prow.residual_limb__sensation": {"en": "Sensation", "ar": "الإحساس"},
    "prow.assessment__joint_range": {"en": "Joint range", "ar": "مدى حركة المفاصل"},
    "prow.assessment__strength": {"en": "Strength", "ar": "القوة العضلية"},
    "prow.contralateral_limb_status": {"en": "Other leg", "ar": "الساق الأخرى"},
    "prow.assessment__other_foot_neuropathy": {"en": "Other foot: neuropathy", "ar": "القدم الأخرى: اعتلال الأعصاب"},
    "prow.assessment__diabetic_foot_team": {
        "en": "Other foot: under the diabetic foot team's care",
        "ar": "القدم الأخرى: تحت رعاية فريق القدم السكرية",
    },
    "prow.assessment__goal_participation": {"en": "Participation goal", "ar": "هدف المشاركة"},
    "prow.assessment__goal_body_function": {"en": "Body function goal", "ar": "هدف وظائف الجسم"},
    "prow.assessment__home_work_setting": {"en": "Home and work setting", "ar": "بيئة المنزل والعمل"},
    "req_group.body": {"en": "Residual limb and body", "ar": "الطرف المتبقي والجسم"},
    "req_group.goals": {"en": "Goals, function and setting", "ar": "الأهداف والوظيفة والبيئة"},
    "preq.conflict_note": {"en": "Note (the prosthetist's words)", "ar": "ملاحظة (بكلمات أخصائي الأطراف الاصطناعية)"},
    "pcomp.title": {
        "en": "Functional requirements and component support",
        "ar": "المتطلبات الوظيفية ودعم اختيار المكونات",
    },
    "pcomp.intro": {
        "en": "What the prosthesis must do, then the options for each component side by side. Never ranked: the prosthetist chooses and records why.",
        "ar": "ما يجب أن يؤديه الطرف الاصطناعي، ثم خيارات كل مكوّن جنباً إلى جنب. دون ترتيب: يختار أخصائي الأطراف الاصطناعية ويسجّل السبب.",
    },
    "pcomp.requirements": {"en": "Functional requirements", "ar": "المتطلبات الوظيفية"},
    "pcomp.requirements_note": {
        "en": "Each one what the prosthesis must do, never a device, written by the prosthetist and tied to where it came from in the case; the prosthetist sets the priority.",
        "ar": "كل متطلب ما يجب أن يؤديه الطرف الاصطناعي لا جهاز بعينه، يكتبه أخصائي الأطراف الاصطناعية ويربطه بمصدره في الحالة؛ ويحدّد الأخصائي الأولوية.",
    },
    "pcomp.components": {"en": "Components", "ar": "المكونات"},
    "pcomp.components_note": {
        "en": "For each component of this amputation level, up to three options typed by the prosthetist, in the order entered.",
        "ar": "لكل مكوّن من مكونات مستوى البتر هذا، حتى ثلاثة خيارات يكتبها أخصائي الأطراف الاصطناعية، بترتيب إدخالها.",
    },
    "pcomp.side_by_side": {"en": "Side by side, never ranked", "ar": "جنباً إلى جنب، دون ترتيب"},
    "pcomp.in_configuration": {"en": "in the configuration", "ar": "ضمن التشكيلة"},
    "pcomp.addresses": {
        "en": "Addresses (the prosthetist's marks)",
        "ar": "ما يلبّيه (تقدير أخصائي الأطراف الاصطناعية)",
    },
    "pcomp.unaddressed": {
        "en": "Marked by the prosthetist as not addressing a Must requirement: {ids}",
        "ar": "قدّر أخصائي الأطراف الاصطناعية أنه لا يلبّي متطلباً ضرورياً: {ids}",
    },
    "pcomp.costs": {"en": "What it costs the person", "ar": "ما يكلّفه للشخص"},
    "pcomp.sources": {"en": "Sources linked", "ar": "المصادر المربوطة"},
    "pcomp.no_source_linked": {"en": "No source linked.", "ar": "لم يُربط مصدر."},
    "pcomp.funding": {"en": "Funding rule, as the payer prints it", "ar": "قاعدة التمويل، كما تطبعها الجهة الدافعة"},
    "pcomp.weight_limit": {
        "en": "Maker's weight limit (kg), as printed",
        "ar": "حد الوزن لدى الصانع (كغ)، كما هو مطبوع",
    },
    "pcomp.weight_vs": {
        "en": "Maker's limit {limit} kg · recorded weight {weight} kg",
        "ar": "حد الصانع {limit} كغ · الوزن المسجَّل {weight} كغ",
    },
    "pcomp.weight_not_recorded": {"en": "The person's weight is not recorded.", "ar": "وزن الشخص غير مسجَّل."},
    "pcomp.above_limit": {
        "en": "The recorded weight is above the maker's limit as entered.",
        "ar": "الوزن المسجَّل أعلى من حد الصانع كما أُدخل.",
    },
    "pcomp.stock": {"en": "Clinic stock and lead time", "ar": "مخزون العيادة ومدة التوريد"},
    "pcomp.checks": {"en": "Check at fitting", "ar": "ما يُتحقق منه عند التركيب"},
    "pcomp.notes": {"en": "Notes", "ar": "ملاحظات"},
    "pcomp.no_options": {"en": "No option entered yet.", "ar": "لم يُدخل خيار بعد."},
    "pcomp.what_sources_say": {
        "en": "What the sources say about this component",
        "ar": "ما تقوله المصادر عن هذا المكوّن",
    },
    "pcomp.edit": {"en": "Enter or change the options", "ar": "أدخل الخيارات أو عدّلها"},
    "pcomp.option_name": {
        "en": "Option, as the prosthetist names it",
        "ar": "الخيار، كما يسمّيه أخصائي الأطراف الاصطناعية",
    },
    "pcomp.link_sources": {"en": "Link the sources shown for it", "ar": "اربط المصادر المعروضة له"},
    "pcomp.empty_removes": {
        "en": "Empty an option's name to remove it. Costs and checks: one per line.",
        "ar": "أفرغ اسم الخيار لحذفه. التكاليف وما يُتحقق منه: سطر لكل بند.",
    },
    "pcomp.save_options": {"en": "Save the options: {component}", "ar": "احفظ الخيارات: {component}"},
    "pcomp.configuration": {"en": "The prosthetist's configuration", "ar": "تشكيلة أخصائي الأطراف الاصطناعية"},
    "pcomp.configuration_note": {
        "en": "Recorded with the requirements and the sources shown at the time",
        "ar": "تُسجَّل مع المتطلبات والمصادر المعروضة وقتها",
    },
    "pcomp.not_chosen": {"en": "Not chosen", "ar": "لم يُختر"},
    "pcomp.recorded_with": {
        "en": "The configuration and its reason are kept in the review log with the requirements, the options and what the review page shows, as they are now.",
        "ar": "تُحفظ التشكيلة وسببها في سجل المراجعة مع المتطلبات والخيارات وما تعرضه صفحة المراجعة، كما هي الآن.",
    },
    "pcomp.record": {"en": "Record and go to design →", "ar": "سجّل وانتقل إلى التصميم ←"},
    "pcomp.back": {"en": "← Back to the assessment", "ar": "→ العودة إلى التقييم"},
    "pcomp.logged": {
        "en": "Configurations logged: {n}, the last at {at} (UTC).",
        "ar": "التشكيلات المسجَّلة: {n}، آخرها في {at} (UTC).",
    },
    "pcomp.choice_logged": {
        "en": "The configuration and its reason are in the review log.",
        "ar": "التشكيلة وسببها في سجل المراجعة.",
    },
    "pcomp.reason_was": {"en": "Reason recorded:", "ar": "السبب المسجَّل:"},
    "pcomp.reason": {"en": "Reason", "ar": "السبب"},
    "pfit.title": {"en": "Design and fitting decisions", "ar": "قرارات التصميم والتركيب"},
    "pfit.intro": {
        "en": "Each step logs what was seen and what was changed. Possible causes come in the sources' own words; the prosthetist picks the adjustment.",
        "ar": "تسجّل كل خطوة ما شوهد وما غُيّر. تأتي الأسباب المحتملة بكلمات المصادر؛ ويختار أخصائي الأطراف الاصطناعية التعديل.",
    },
    "pfit.configuration": {"en": "Configuration:", "ar": "التشكيلة:"},
    "pfit.no_configuration": {"en": "No configuration recorded yet.", "ar": "لم تُسجَّل تشكيلة بعد."},
    "pfit.to_configuration": {"en": "Record it in modules 2–3 →", "ar": "سجّلها في الوحدتين 2–3 ←"},
    "pfit.steps": {"en": "Fitting steps", "ar": "خطوات التركيب"},
    "pfit.steps_edit": {"en": "Update the steps", "ar": "حدّث الخطوات"},
    "pfit.step_notes": {"en": "Notes (e.g. method, approved)", "ar": "ملاحظات (مثلاً الطريقة، الاعتماد)"},
    "pfit.save_steps": {"en": "Save the steps", "ar": "احفظ الخطوات"},
    "pfit.observations": {"en": "Observation log", "ar": "سجل الملاحظات"},
    "pfit.observations_note": {
        "en": "What was seen, with its gait phase, the adjustment made and what was seen after",
        "ar": "ما شوهد مع مرحلة المشية، والتعديل الذي أُجري، وما شوهد بعده",
    },
    "pfit.step": {"en": "Step", "ar": "الخطوة"},
    "pfit.seen": {"en": "Seen", "ar": "ما شوهد"},
    "pfit.adjustment": {
        "en": "Adjustment made by the prosthetist",
        "ar": "التعديل الذي أجراه أخصائي الأطراف الاصطناعية",
    },
    "pfit.seen_after": {"en": "What was seen after", "ar": "ما شوهد بعده"},
    "pfit.phase": {"en": "Gait phase", "ar": "مرحلة المشية"},
    "pfit.no_phase": {"en": "No phase", "ar": "دون مرحلة"},
    "pfit.no_observations": {"en": "No observation logged yet.", "ar": "لم تُسجَّل ملاحظة بعد."},
    "pfit.causes": {"en": "Possible causes, as the sources list them", "ar": "الأسباب المحتملة، كما تذكرها المصادر"},
    "pfit.observations_edit": {"en": "Log or change observations", "ar": "سجّل الملاحظات أو عدّلها"},
    "pfit.observation_n": {"en": "Observation {n}", "ar": "الملاحظة {n}"},
    "pfit.empty_removes": {
        "en": "Empty what was seen to remove an observation.",
        "ar": "أفرغ «ما شوهد» لحذف الملاحظة.",
    },
    "pfit.save_observations": {"en": "Save the observation log", "ar": "احفظ سجل الملاحظات"},
    "pfit.socket": {"en": "Check-socket versions", "ar": "إصدارات التجويف التجريبي"},
    "pfit.version": {"en": "Version", "ar": "الإصدار"},
    "pfit.socket_seen": {"en": "Seen", "ar": "ما شوهد"},
    "pfit.socket_changed": {"en": "Changed", "ar": "ما غُيّر"},
    "pfit.no_socket": {"en": "No check-socket version yet.", "ar": "لا إصدار للتجويف التجريبي بعد."},
    "pfit.socket_add": {"en": "Add version {n}", "ar": "أضف الإصدار {n}"},
    "pfit.versions_kept": {
        "en": "A version is added, never changed: every earlier one is kept.",
        "ar": "يُضاف الإصدار ولا يُغيَّر: يُحتفظ بكل إصدار سابق.",
    },
    "pfit.save_socket": {"en": "Add the version", "ar": "أضف الإصدار"},
    "pfit.definitive": {"en": "Before a definitive prosthesis", "ar": "قبل الطرف الاصطناعي النهائي"},
    "pfit.definitive_note": {
        "en": "What the case recorded and what the guideline says. The prosthetist decides when.",
        "ar": "ما سجّلته الحالة وما يقوله الدليل. ويقرر أخصائي الأطراف الاصطناعية متى.",
    },
    "pfit.checklist_not_set": {
        "en": "The clinic's own checklist is not set yet: it is the owner's to set (SYSTEM_DESIGN.md §11.3).",
        "ar": "لم تُحدَّد قائمة التحقق الخاصة بالعيادة بعد: تحديدها للمالك (SYSTEM_DESIGN.md §11.3).",
    },
    "pfit.case_recorded": {"en": "What the case recorded", "ar": "ما سجّلته الحالة"},
    "pfit.guideline_says": {"en": "What the sources say about readiness", "ar": "ما تقوله المصادر عن الجاهزية"},
    "pfit.alignment": {"en": "Alignment record", "ar": "سجل المحاذاة"},
    "pfit.alignment_version": {"en": "Version {n}, {date}", "ar": "الإصدار {n}، {date}"},
    "pfit.no_alignment": {"en": "No alignment recorded yet.", "ar": "لم تُسجَّل محاذاة بعد."},
    "pfit.alignment_note": {
        "en": "Values entered by the prosthetist; every change is kept.",
        "ar": "قيم يُدخلها أخصائي الأطراف الاصطناعية؛ ويُحتفظ بكل تغيير.",
    },
    "pfit.alignment_history": {"en": "Every version ({n})", "ar": "كل الإصدارات ({n})"},
    "pfit.alignment_edit": {"en": "Record a new version", "ar": "سجّل إصداراً جديداً"},
    "pfit.align_name": {"en": "What was aligned", "ar": "ما ضُبط"},
    "pfit.align_value": {"en": "Value", "ar": "القيمة"},
    "pfit.align_note": {"en": "Why it changed", "ar": "سبب التغيير"},
    "pfit.align_by": {"en": "Saved by", "ar": "حفظه"},
    "pfit.save_alignment": {"en": "Save as a new version", "ar": "احفظ كإصدار جديد"},
    "pfit.fabrication_sheet": {"en": "Export the fabrication sheet", "ar": "صدّر ورقة التصنيع"},
    "pfit.to_follow_up": {"en": "Set up follow-up →", "ar": "أعدّ المتابعة ←"},
    "pstep.shape_capture": {"en": "Shape capture", "ar": "أخذ شكل الطرف"},
    "pstep.check_socket": {"en": "Check socket", "ar": "التجويف التجريبي"},
    "pstep.bench_alignment": {"en": "Bench alignment", "ar": "المحاذاة على الطاولة"},
    "pstep.static_alignment": {"en": "Static alignment", "ar": "المحاذاة الثابتة"},
    "pstep.dynamic_alignment": {"en": "Dynamic alignment", "ar": "المحاذاة أثناء المشي"},
    "pstep.delivery": {"en": "Delivery", "ar": "التسليم"},
    "pfu.title": {"en": "Follow-up and evaluation", "ar": "المتابعة والتقييم"},
    "pfu.intro": {
        "en": "Values shown as recorded at each visit. The prosthetist judges the change.",
        "ar": "تُعرض القيم كما سُجِّلت في كل زيارة. ويقدّر أخصائي الأطراف الاصطناعية التغيّر.",
    },
    "pfu.refit": {"en": "Refit the socket", "ar": "أعد تركيب التجويف"},
    "pfu.review_components": {"en": "Review the components", "ar": "راجع المكونات"},
    "fu.back_to.fitting": {"en": "Refit in design and fitting →", "ar": "أعد التركيب في التصميم والتركيب ←"},
    "fu.back_to.components": {"en": "Review in requirements and components →", "ar": "راجع في المتطلبات والمكونات ←"},
    "fu.back_to.assess": {"en": "Re-assess in the assessment →", "ar": "أعد التقييم في تقييم الحالة ←"},
    "error.mobility_needs_name_value": {
        "en": "A mobility measure needs its test and its result.",
        "ar": "يحتاج مقياس التنقل إلى اسم الاختبار ونتيجته.",
    },
    "error.option_needs_name": {"en": "Option {option} needs its name.", "ar": "يحتاج الخيار {option} إلى اسمه."},
    "error.configuration_needs_option": {
        "en": "A configuration needs at least one option chosen.",
        "ar": "تحتاج التشكيلة إلى خيار مختار واحد على الأقل.",
    },
    "error.observation_needs_seen": {"en": "An observation needs what was seen.", "ar": "تحتاج الملاحظة إلى ما شوهد."},
    "error.observation_needs_step": {"en": "An observation needs its step.", "ar": "تحتاج الملاحظة إلى خطوتها."},
    "error.alignment_needs_both": {
        "en": "Each alignment value needs both what was aligned and its value.",
        "ar": "تحتاج كل قيمة محاذاة إلى ما ضُبط وقيمته معاً.",
    },
    "error.alignment_repeated": {"en": "{name} is listed twice.", "ar": "{name} مذكور مرتين."},
    "error.no_alignment_change": {
        "en": "Nothing changed since the last version: no new version saved.",
        "ar": "لم يتغيّر شيء منذ الإصدار الأخير: لم يُحفظ إصدار جديد.",
    },
    "error.socket_needs_seen": {
        "en": "A check-socket version needs what was seen.",
        "ar": "يحتاج إصدار التجويف التجريبي إلى ما شوهد.",
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
        # Orthotics (orthotics/fields.py FIELDS; core paths above are shared)
        "months_since_onset": "المدة منذ السكتة الدماغية",
        "functional_goals": "الأهداف الوظيفية",
        "exam.dorsiflexion_knee_extended_deg": "العطف الظهري للكاحل والركبة ممدودة",
        "exam.dorsiflexion_knee_flexed_deg": "العطف الظهري للكاحل والركبة مثنية",
        "exam.protective_sensation": "الإحساس الوقائي في القدم",
        "exam.skin_condition": "جلد القدم والساق",
        "walking.status": "حالة المشي",
        "walking.gait_speed_m_s": "سرعة المشي (مع اسم الاختبار)",
        "exam.plantarflexor_tone_grade": "توتر العضلات المثنية للأخمص (المقياس والدرجة)",
        "exam.dorsiflexor_strength": "قوة العضلات العاطفة الظهرية",
        "exam.knee_extensor_strength": "قوة باسطات الركبة",
        "exam.knee_in_stance": "الركبة في مرحلة الارتكاز (فرط البسط أو الانثناء)",
        "walking.deviations": "انحرافات المشية حسب المرحلة",
        "walking.falls_last_6_months": "السقوط",
        "exam.foot_posture": "وضعية القدم (مرنة أو متيبسة)",
        "exam.proprioception": "الحس العميق",
        "footwear": "الحذاء",
        "donning": "ارتداء الجهاز التقويمي",
        "prior_orthoses": "أجهزة تقويمية أو تنبيه كهربائي سابق",
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
        # Orthotics
        "OrthoticCondition": {"stroke": "سكتة دماغية"},
        "WalkingStatus": {
            "non_ambulatory": "لا يمشي",
            "with_assistance": "يمشي بمساعدة شخص آخر",
            "independent_with_aid": "يمشي وحده بأداة مساعدة",
            "independent": "يمشي وحده دون أداة",
            "unknown": "غير معروف",
        },
        "KneeInStance": {"stable": "مستقرة", "hyperextends": "فرط بسط", "buckles": "انثناء مفاجئ",
                         "unknown": "غير معروف"},
        "SensationStatus": {"intact": "سليم", "reduced": "منخفض", "absent": "غائب", "unknown": "غير معروف"},
        "ToneScale": {"modified_ashworth": "مقياس آشورث المعدّل", "modified_tardieu": "مقياس تارديو المعدّل",
                      "other": "مقياس آخر"},
        "DonningAbility": {"independent": "وحده", "needs_help": "يحتاج إلى مساعدة", "unknown": "غير معروف"},
        "YesNoUnknown": {"yes": "نعم", "no": "لا", "unknown": "غير معروف"},
        "GaitDeviation": {
            "foot_flat_contact": "تلامس القدم مسطحةً مع الأرض",
            "knee_hyperextension": "فرط بسط الركبة",
            "knee_buckling": "انثناء الركبة المفاجئ",
            "no_heel_rise": "عدم ارتفاع الكعب",
            "reduced_push_off": "ضعف الدفع",
            "toe_drag": "جرّ أصابع القدم (تدلي القدم)",
            "circumduction": "رفع الورك أو الدوران الخارجي للساق (تعويض)",
        },
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


def set_language_cookie(response, lang: str) -> None:
    """Remember the chosen language in the browser."""
    response.set_cookie(LANGUAGE_COOKIE, lang, max_age=LANGUAGE_COOKIE_DAYS * 24 * 3600, samesite="Lax")


class TextKey(str):
    """A TEXT key given to TranslatableError, e.g. a form label: shown in the page's language."""


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
        # A wrapped error (e.g. a device row's own error) and a label are translated too.
        params = {name: _translated(value, lang) for name, value in self.params.items()}
        return t(self.key, lang, **params)


def _translated(value, lang: str):
    if isinstance(value, TranslatableError):
        return value.message(lang)
    if isinstance(value, TextKey):
        return t(value, lang)
    return value


def error_message(error: Exception, lang: str) -> str:
    """The message to show for an error: translated if it can be."""
    return error.message(lang) if isinstance(error, TranslatableError) else str(error)
