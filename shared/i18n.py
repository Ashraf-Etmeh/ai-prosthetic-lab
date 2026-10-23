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
    "nav.other_language": {"en": "العربية", "ar": "English"},
    "nav.other_code": {"en": "ar", "ar": "en"},
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
    # Design and fitting (reasoning/fitting_support.py)
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
    "map.title": {"en": "Orthotics: the modules", "ar": "تقويم العظام: الوحدات"},
    "map.intro": {
        "en": "Function first, device second. Each module is one step from the case to the design, and the "
              "orthotist decides at every step.",
        "ar": "الوظيفة أولاً ثم الجهاز. كل وحدة خطوة من الحالة إلى التصميم، وأخصائي التقويم يقرر في كل خطوة.",
    },
    "map.chain_heading": {"en": "From the case to the design", "ar": "من الحالة إلى التصميم"},
    "map.principle": {
        "en": "The tool shows the case, what the orthotist writes and what the sources say: never a prescription.",
        "ar": "تعرض الأداة الحالة وما يكتبه أخصائي التقويم وما تقوله المصادر: لا وصفة أبداً.",
    },
    "map.module": {"en": "Module {n}", "ar": "الوحدة {n}"},
    "map.in_brief": {"en": "In the brief:", "ar": "في الموجز:"},
    "map.bridge": {"en": "The bridge between the analysis and the design.", "ar": "الجسر بين التحليل والتصميم."},
    "map.new_case": {"en": "New orthotic case", "ar": "حالة تقويمية جديدة"},
    "map.from_case": {
        "en": "Opened from an orthotic case's pages, in the header.",
        "ar": "تُفتح من صفحات الحالة التقويمية، من الشريط العلوي.",
    },
    "map.not_built_heading": {"en": "Not built yet", "ar": "لم تُبنَ بعد"},
    "map.not_built": {
        "en": "From the same design: fit, tune and train (module 5: check-out, tuning, training plan, patient "
              "leaflet) and follow-up (module 6: outcome measures over time, alerts). Follow-up needs a way to link "
              "visits without identifying the patient first.",
        "ar": "من التصميم نفسه: التركيب والضبط والتدريب (الوحدة 5: الفحص عند التسليم والضبط وخطة التدريب ونشرة "
              "المريض) والمتابعة (الوحدة 6: مقاييس النتائج عبر الزمن والتنبيهات). تحتاج المتابعة أولاً إلى طريقة لربط "
              "الزيارات دون التعريف بالمريض.",
    },
    "chain.impairments": {"en": "Impairments and goals", "ar": "الإعاقات والأهداف"},
    "chain.gait": {"en": "Problems by gait phase", "ar": "المشكلات حسب مرحلة المشي"},
    "chain.requirements": {"en": "What the orthosis must do", "ar": "ما يجب أن يؤديه الجهاز"},
    "chain.options": {"en": "Design options", "ar": "خيارات التصميم"},
    "chain.design": {"en": "Design and fabrication", "ar": "التصميم والتصنيع"},
    "chain_module.impairments": {"en": "Module 1 · case analysis", "ar": "الوحدة 1 · تحليل الحالة"},
    "chain_module.gait": {"en": "Module 1 · gait observed by phase", "ar": "الوحدة 1 · ملاحظة المشي حسب المرحلة"},
    "chain_module.requirements": {"en": "Module 2 · requirements", "ar": "الوحدة 2 · المتطلبات"},
    "chain_module.options": {"en": "Module 3 · options, not orders", "ar": "الوحدة 3 · خيارات لا أوامر"},
    "chain_module.design": {"en": "Module 4 · digital or conventional", "ar": "الوحدة 4 · رقمي أو تقليدي"},
    "map_name.analyse": {"en": "Functional case analysis", "ar": "تحليل الحالة الوظيفية"},
    "map_name.requirements": {"en": "Functional requirements", "ar": "المتطلبات الوظيفية"},
    "map_name.options": {"en": "Design options, components and materials", "ar": "خيارات التصميم والمكونات والمواد"},
    "map_name.design": {"en": "Digital design workflow", "ar": "سير عمل التصميم الرقمي"},
    "map_does.analyse": {
        "en": "The orthotic intake (the exam, and gait observed phase by phase), the information still needed with "
              "what the sources say about why, and what they say about an orthosis or FES and about design and fitting.",
        "ar": "استمارة الحالة التقويمية (الفحص، والمشي ملاحظاً مرحلةً مرحلة)، والمعلومات التي ما زالت مطلوبة مع ما "
              "تقوله المصادر عن سببها، وما تقوله عن جهاز التقويم أو التنبيه الكهربائي وعن التصميم والتركيب.",
    },
    "map_does.requirements": {
        "en": "Each problem becomes what the orthosis must do, in the orthotist's words, tied to the findings it "
              "comes from; the orthotist sets the priority.",
        "ar": "تصبح كل مشكلة ما يجب أن يؤديه الجهاز، بكلمات أخصائي التقويم، مربوطةً بالنتائج التي جاءت منها؛ ويحدد "
              "أخصائي التقويم الأولوية.",
    },
    "map_does.options": {
        "en": "Up to three options side by side, never ranked: each device type with its materials and parts, each "
              "part tied to the requirements it serves and so to the case, and what the sources say about each. The "
              "orthotist chooses and records why.",
        "ar": "حتى ثلاثة خيارات جنباً إلى جنب دون ترتيب: لكل نوع جهاز موادّه ومكوناته، وكل مكوّن مربوط بالمتطلبات "
              "التي يخدمها ومن ثَمّ بالحالة، مع ما تقوله المصادر عن كلٍّ منها. يختار أخصائي التقويم ويسجّل السبب.",
    },
    "map_does.design": {
        "en": "The steps from capture to release with their status and method, and the design parameters the "
              "orthotist sets, every save kept as a version, with what the sources say about each step.",
        "ar": "الخطوات من أخذ الشكل إلى التسليم مع حالتها وطريقتها، ومعايير التصميم التي يحددها أخصائي التقويم، "
              "وكل حفظ يُبقى نسخةً، مع ما تقوله المصادر عن كل خطوة.",
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
    "req.no_findings": {"en": "Nothing recorded for this case yet.", "ar": "لم يُسجَّل شيء لهذه الحالة بعد."},
    "req.new": {"en": "New", "ar": "جديد"},
    "req.priority_unset": {"en": "Not set", "ar": "غير محددة"},
    "req.empty_removes": {
        "en": "Write a new requirement in an empty row. Empty a requirement's text to remove it.",
        "ar": "اكتب متطلباً جديداً في صف فارغ. أفرغ نص متطلبٍ لحذفه.",
    },
    "req.save": {"en": "Save the requirements", "ar": "احفظ المتطلبات"},
    "req.missing_heading": {"en": "Information still missing (module 1)", "ar": "معلومات ما زالت ناقصة (الوحدة 1)"},
    "req.missing_none": {"en": "None listed.", "ar": "لا شيء مُدرج."},
    "req.traceable_heading": {"en": "Traceable", "ar": "قابل للتتبع"},
    "req.traceable": {
        "en": "Each requirement keeps the findings it came from. On the options page each material and part is tied "
              "to the requirements it serves, so every part leads back to the case.",
        "ar": "يحتفظ كل متطلب بالنتائج التي جاء منها. وفي صفحة الخيارات يُربط كل مادة ومكوّن بالمتطلبات التي يخدمها، "
              "فيعود كل مكوّن إلى الحالة.",
    },
    "req.to_options": {"en": "Design options →", "ar": "خيارات التصميم ←"},
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
        "en": "Up to three options as the orthotist writes them, shown side by side in the order written, never "
              "ranked. Each material and part is tied to the requirements it serves. The orthotist chooses and "
              "records why.",
        "ar": "حتى ثلاثة خيارات كما يكتبها أخصائي التقويم، تُعرض جنباً إلى جنب بترتيب كتابتها دون ترتيب تفضيلي. تُربط "
              "كل مادة ومكوّن بالمتطلبات التي يخدمها. يختار أخصائي التقويم ويسجّل السبب.",
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
        "en": "Recorded in the review log with the requirements, the options and the rest of the plan as they are now.",
        "ar": "يُسجَّل في سجل المراجعة مع المتطلبات والخيارات وبقية الخطة كما هي الآن.",
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
    "design.title": {"en": "Digital design workflow", "ar": "سير عمل التصميم الرقمي"},
    "design.intro": {
        "en": "The steps from capture to release and the design parameters, as the orthotist records them. Every "
              "parameter save is kept as a new version. The tool suggests no step, method or value.",
        "ar": "الخطوات من أخذ الشكل إلى التسليم ومعايير التصميم كما يسجّلها أخصائي التقويم. يُبقى كل حفظ للمعايير نسخةً "
              "جديدة. لا تقترح الأداة خطوةً ولا طريقةً ولا قيمة.",
    },
    "design.chosen": {"en": "Chosen in module 3: {option}", "ar": "المختار في الوحدة 3: {option}"},
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
    "design.not_built": {
        "en": "Not in this version: a 3D scan viewer, pressure maps and simulation (no scan data reaches the app), and "
              "sending to manufacture.",
        "ar": "ليس في هذه النسخة: عارض المسح ثلاثي الأبعاد وخرائط الضغط والمحاكاة (لا تصل بيانات مسح إلى التطبيق)، "
              "والإرسال إلى التصنيع.",
    },
    "step.capture": {"en": "Capture", "ar": "أخذ الشكل"},
    "step.rectify": {"en": "Rectify", "ar": "التعديل"},
    "step.parameters": {"en": "Parameters", "ar": "المعايير"},
    "step.fabricate": {"en": "Fabricate", "ar": "التصنيع"},
    "step.release": {"en": "Release and fit", "ar": "التسليم والتركيب"},
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
    # ---- Every page's header and the prosthetics map (2026-10-23; templates/ui_header.html) ----
    "domain.prosthetics": {"en": "Prosthetics", "ar": "الأطراف الاصطناعية"},
    "domain.orthotics": {"en": "Orthotics", "ar": "تقويم العظام"},
    "domain.switch": {"en": "Domains", "ar": "المجالات"},
    "domain.modules": {"en": "{domain} modules", "ar": "وحدات {domain}"},
    "pmod.evaluate": {"en": "1 Evaluate", "ar": "1 التقييم"},
    "pmod.functional": {"en": "2 Functional level", "ar": "2 المستوى الوظيفي"},
    "pmod.components": {"en": "3 Components", "ar": "3 المكونات"},
    "pmod.fitting": {"en": "4 Design and fitting", "ar": "4 التصميم والتركيب"},
    "pmod.side": {"en": "{side} side", "ar": "الجانب: {side}"},
    "pmod.k_level": {"en": "recorded {k}", "ar": "المسجَّل {k}"},
    "pmod.months": {"en": "{n} months since amputation", "ar": "الأشهر منذ البتر: {n}"},
    "pmod.specialist_decides": {"en": "Decision support: the specialist decides", "ar": "دعم القرار: المختص هو من يقرر"},
    "pmod.review_kicker": {"en": "Modules 1-4 on one page", "ar": "الوحدات 1-4 في صفحة واحدة"},
    "pmap.title": {"en": "Prosthetics: the modules", "ar": "الأطراف الاصطناعية: الوحدات"},
    "pmap.intro": {
        "en": "From the amputation case to design and fitting. Modules 1-4 are the sections of each case's review "
              "page, marked together in one decision; the specialist decides at every step.",
        "ar": "من حالة البتر إلى التصميم والتركيب. الوحدات 1-4 أقسام في صفحة مراجعة كل حالة، تُقدَّر معاً في قرار واحد؛ "
              "والمختص يقرر في كل خطوة.",
    },
    "pmap.new_case": {"en": "New prosthetic case", "ar": "حالة طرف اصطناعي جديدة"},
    "pmap.from_case": {
        "en": "A section of each case's review page; the header links to it.",
        "ar": "قسم في صفحة مراجعة كل حالة؛ ويؤدي إليه الشريط العلوي.",
    },
    "pmap.not_built": {
        "en": "Follow-up and evaluation (the brief's fifth capability) needs a way to link visits without identifying "
              "the patient first.",
        "ar": "تحتاج المتابعة والتقييم (القدرة الخامسة في الموجز) أولاً إلى طريقة لربط الزيارات دون التعريف بالمريض.",
    },
    "pmap.principle": {
        "en": "The tool shows the case and what the sources say, each AI summary over a quote checked word for word: "
              "it never diagnoses, chooses or ranks components, or judges readiness for fitting.",
        "ar": "تعرض الأداة الحالة وما تقوله المصادر، وكل ملخص من الذكاء الاصطناعي فوق اقتباس يُتحقق منه كلمةً كلمة: لا "
              "تشخّص ولا تختار المكونات ولا ترتّبها ولا تحكم على الجاهزية للتركيب.",
    },
    "pmap_name.evaluate": {"en": "Evaluating the amputation case", "ar": "تقييم حالة البتر"},
    "pmap_name.functional": {"en": "Functional level and goals", "ar": "المستوى الوظيفي والأهداف"},
    "pmap_name.components": {"en": "Component selection support", "ar": "دعم اختيار المكونات"},
    "pmap_name.fitting": {"en": "Design and fitting", "ar": "التصميم والتركيب"},
    "pmap_does.evaluate": {
        "en": "The intake form, and the information still needed before evaluation, each with what the sources say "
              "about why (use case 01).",
        "ar": "استمارة الحالة، والمعلومات التي ما زالت مطلوبة قبل التقييم، مع ما تقوله المصادر عن سببها (حالة الاستخدام 01).",
    },
    "pmap_does.functional": {
        "en": "The functional level (K-level) and goals as recorded, and what the sources say about that level.",
        "ar": "المستوى الوظيفي (مستوى K) والأهداف كما سُجّلت، وما تقوله المصادر عن هذا المستوى.",
    },
    "pmap_does.components": {
        "en": "For each prosthetic component, what the sources say for this case, side by side and never chosen or "
              "ranked (use case 02).",
        "ar": "لكل مكوّن من مكونات الطرف الاصطناعي، ما تقوله المصادر عن هذه الحالة، جنباً إلى جنب دون اختيار أو ترتيب "
              "(حالة الاستخدام 02).",
    },
    "pmap_does.fitting": {
        "en": "Readiness for fitting, a preparatory or definitive prosthesis, the fitting steps and alignment: what the "
              "sources say, next to what the case recorded.",
        "ar": "الجاهزية للتركيب، والطرف المؤقت أو النهائي، وخطوات التركيب والمحاذاة: ما تقوله المصادر بجانب ما سجّلته الحالة.",
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
        # Orthotics (shared/field_guide.py ORTHOTIC_FIELDS; core paths above are shared)
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
