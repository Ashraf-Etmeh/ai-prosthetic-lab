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
        "en": "Required when approving with edits: what should change",
        "ar": "مطلوبة عند الاعتماد مع تعديلات: ما الذي يجب تغييره",
    },
    "review.approve": {"en": "Approve as reviewed", "ar": "اعتماد كما رُوجع"},
    "review.edit": {"en": "Approve with edits", "ar": "اعتماد مع تعديلات"},
    "review.reject": {"en": "Reject the analysis", "ar": "رفض التحليل"},
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
    "decision.approve": {"en": "approve as reviewed", "ar": "اعتماد كما رُوجع"},
    "decision.edit": {"en": "approve with edits", "ar": "اعتماد مع تعديلات"},
    "decision.reject": {"en": "reject the analysis", "ar": "رفض التحليل"},
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
        "en": "Approving with edits needs a note saying what should change.",
        "ar": "الاعتماد مع تعديلات يحتاج إلى ملاحظة توضح ما الذي يجب تغييره.",
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
    "domain.switch": {"en": "Parts of the system", "ar": "أجزاء النظام"},
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
    # ---- The reasoning and review pages (plan Part 4, 2026-10-25; review/routes.py, quality/measures.py) ----
    "part.review": {"en": "Reasoning and review", "ar": "الاستدلال والمراجعة"},
    "rmod.pathway": {"en": "1 Pathway", "ar": "1 المسار"},
    "rmod.review": {"en": "2 Review", "ar": "2 المراجعة"},
    "rmod.quality": {"en": "3 Quality and audit", "ar": "3 الجودة والتدقيق"},
    "review.note": {"en": "Note", "ar": "ملاحظة"},
    "review.sign": {"en": "Sign and record", "ar": "وقّع وسجّل"},
    "review.recorded_once": {
        "en": "Recorded once, never edited: the case, every item as shown with its quote and passage, the marks, and the model, prompt and library versions.",
        "ar": "يُسجَّل مرة واحدة ولا يُعدَّل: الحالة، وكل بند كما عُرض مع اقتباسه ومقطعه، والتقديرات، وإصدارات النموذج والتعليمات والمكتبة.",
    },
    "review.summary_wrong": {"en": "Summary is wrong", "ar": "الملخص خاطئ"},
    "review.why": {"en": "Why (kept with the case)", "ar": "السبب (يُحفظ مع الحالة)"},
    "review.library_version": {
        "en": "Source library built {built}, {n} passages",
        "ar": "مكتبة المصادر المبنية في {built}، المقاطع: {n}",
    },
    "summary.summary_wrong": {"en": "{n} summary wrong", "ar": "الملخص خاطئ: {n}"},
    "error.choose_decision": {
        "en": "Choose approve as reviewed, approve with edits or reject the analysis.",
        "ar": "اختر الاعتماد كما رُوجع أو الاعتماد مع تعديلات أو رفض التحليل.",
    },
    "error.reason_too_long": {"en": "A reason: at most {n} characters.", "ar": "السبب: {n} حرفاً على الأكثر."},
    "path.title": {"en": "The reasoning pathway and its guardrails", "ar": "مسار الاستدلال وضوابطه"},
    "path.kicker": {"en": "Shared by every domain", "ar": "مشترك بين كل المجالات"},
    "path.intro": {
        "en": "Six steps from the case to the documented outcome. Each step says what it produces and what stops it from overstepping.",
        "ar": "ست خطوات من الحالة إلى النتيجة الموثَّقة. تذكر كل خطوة ما تنتجه وما يمنعها من تجاوز حدّها.",
    },
    "path_step.case_data": {"en": "Case data", "ar": "بيانات الحالة"},
    "path_step.analysis": {"en": "Information analysis", "ar": "تحليل المعلومات"},
    "path_step.reasoning": {"en": "Specialised reasoning", "ar": "الاستدلال المتخصص"},
    "path_step.output": {"en": "Assistive output", "ar": "توصيات مساعدة"},
    "path_step.review": {"en": "Specialist review", "ar": "مراجعة المختص"},
    "path_step.outcome": {"en": "Documented outcome", "ar": "توثيق النتيجة"},
    "path_does.case_data": {
        "en": "Coded fields with how each was measured; typed text stays on this machine.",
        "ar": "حقول مرمَّزة مع طريقة قياس كل منها؛ ويبقى النص المكتوب على هذا الجهاز.",
    },
    "path_does.analysis": {
        "en": "What is missing, and the passages each topic finds in the library.",
        "ar": "ما ينقص، والمقاطع التي يجدها كل موضوع في المكتبة.",
    },
    "path_does.reasoning": {
        "en": "The clinic's rules, then a language model summarising the passages.",
        "ar": "قواعد العيادة، ثم نموذج لغوي يلخّص المقاطع.",
    },
    "path_does.output": {
        "en": "Gaps, options side by side and checks, each with its source.",
        "ar": "المعلومات الناقصة والخيارات جنباً إلى جنب والفحوص، كلٌّ مع مصدره.",
    },
    "path_does.review": {
        "en": "The specialist marks each item and decides, with a note.",
        "ar": "يقدّر المختص كل بند ويقرر، مع ملاحظة.",
    },
    "path_does.outcome": {
        "en": "The decision, signed, with everything that was shown.",
        "ar": "القرار موقَّعاً، مع كل ما عُرض.",
    },
    "path_guard.case_data": {"en": "Guard: no identifiers", "ar": "الضابط: لا معرِّفات شخصية"},
    "path_guard.analysis": {"en": "Guard: local search only", "ar": "الضابط: بحث محلي فقط"},
    "path_guard.reasoning": {
        "en": "Guard: every quote checked word for word",
        "ar": "الضابط: كل اقتباس يُتحقق منه كلمةً كلمة",
    },
    "path_guard.output": {"en": "Guard: never ranked, never prescribed", "ar": "الضابط: لا ترتيب ولا وصف"},
    "path_guard.review": {"en": "Guard: nothing acts without it", "ar": "الضابط: لا شيء ينفَّذ دونها"},
    "path_guard.outcome": {"en": "Guard: append-only record", "ar": "الضابط: سجل يُضاف إليه فقط"},
    "path.never": {"en": "What the system never outputs", "ar": "ما لا يُخرجه النظام أبداً"},
    "path_never.diagnosis": {"en": "A diagnosis", "ar": "تشخيصاً"},
    "path_never.prescription": {
        "en": "A prescription, a dose or a device setting",
        "ar": "وصفة أو جرعة أو ضبطاً للجهاز",
    },
    "path_never.ranking": {"en": "A ranking of components or options", "ar": "ترتيباً للمكونات أو الخيارات"},
    "path_never.readiness": {
        "en": "Whether a person is ready for fitting or discharge",
        "ar": "حكماً بجاهزية الشخص للتركيب أو للخروج",
    },
    "path_never.unquoted": {"en": "A sentence without a quote behind it", "ar": "جملة لا يسندها اقتباس"},
    "path.checks": {"en": "Checks every answer passes", "ar": "الفحوص التي تمر بها كل إجابة"},
    "path_check.quote": {
        "en": "Quote check: the quote is in its passage, word for word",
        "ar": "فحص الاقتباس: الاقتباس موجود في مقطعه كلمةً كلمة",
    },
    "path_check.advice": {
        "en": "Advice check: no instruction, dose or setting",
        "ar": "فحص النصيحة: لا تعليمات ولا جرعة ولا ضبط",
    },
    "path_check.population": {
        "en": "Population check: the source's own population named",
        "ar": "فحص الفئة: تُذكر الفئة التي يتناولها المصدر نفسه",
    },
    "path_check.hard_stops": {
        "en": "Hard stops: the clinic's rules, versioned",
        "ar": "التوقفات الإلزامية: قواعد العيادة بإصداراتها",
    },
    "path_built.quote": {
        "en": "Built: a sentence whose quote fails is removed before it is shown.",
        "ar": "مبني: تُحذف الجملة التي يفشل اقتباسها قبل عرضها.",
    },
    "path_built.advice": {
        "en": "Measured only: directive wording in the AI's kept sentences is counted (python -m reasoning.sentence_checks); nothing is flagged on the page until the owner approves the patterns.",
        "ar": "يُقاس فقط: تُعدّ صيغ التوجيه في جمل الذكاء الاصطناعي المحتفَظ بها (python -m reasoning.sentence_checks)؛ ولا يُعلَّم شيء في الصفحة حتى يعتمد المالك الأنماط.",
    },
    "path_built.population": {
        "en": "Not built: a source's population is set only from the owner's values; none is shown yet.",
        "ar": "غير مبني: لا تُحدَّد فئة المصدر إلا من قيم المالك؛ ولا يُعرض منها شيء بعد.",
    },
    "path_built.hard_stops": {
        "en": "Applied to what was recorded, each with its status from the owner's file: {drafts} draft, {approved} approved. A rule that matches routes the case to a person.",
        "ar": "تُطبَّق على ما سُجِّل، وكلٌّ مع حالته من ملف المالك: مسوّدة {drafts}، معتمدة {approved}. والقاعدة التي تنطبق تحيل الحالة إلى شخص.",
    },
    "path.data": {"en": "Where data goes", "ar": "أين تذهب البيانات"},
    "path_data.search": {"en": "Search", "ar": "البحث"},
    "path_data.library": {
        "en": "on this machine · library built {built}, {n} passages",
        "ar": "على هذا الجهاز · مكتبة مبنية في {built}، المقاطع: {n}",
    },
    "path_data.no_library": {
        "en": "on this machine · the library is not built yet",
        "ar": "على هذا الجهاز · لم تُبنَ المكتبة بعد",
    },
    "path_data.model": {"en": "Language model, behind one swap point", "ar": "النموذج اللغوي، خلف نقطة تبديل واحدة"},
    "path_data.switched_off": {"en": "switched off on this machine", "ar": "متوقف على هذا الجهاز"},
    "path_data.cloud_on": {"en": "sent to the cloud model", "ar": "يُرسل إلى النموذج السحابي"},
    "path_data.cloud_off": {"en": "not sent: switched off by the owner", "ar": "لا يُرسل: أوقفه المالك"},
    "path_data.never_typed": {
        "en": "Nothing typed is ever sent: no notes, no free text.",
        "ar": "لا يُرسل أي نص مكتوب أبداً: لا ملاحظات ولا نص حر.",
    },
    "path_sends.prosthetics": {
        "en": "Prosthetics sends the amputation level, side and recorded K-level, with the passages.",
        "ar": "يرسل مجال الأطراف الاصطناعية مستوى البتر والجانب والمستوى الوظيفي المسجَّل، مع المقاطع.",
    },
    "path_sends.orthotics": {
        "en": "Orthotics, once switched on, sends the condition, side and months since onset, with the passages.",
        "ar": "يرسل مجال تقويم العظام، بعد تشغيله، الحالة المرضية والجانب والأشهر منذ البداية، مع المقاطع.",
    },
    "path.owner": {
        "en": "The owner switches each domain on for the cloud, and sets the clinic's rules and their versions.",
        "ar": "يشغّل المالك كل مجال للنموذج السحابي، ويحدّد قواعد العيادة وإصداراتها.",
    },
    "qual.title": {"en": "Quality and audit", "ar": "الجودة والتدقيق"},
    "qual.kicker": {"en": "Measured before every release", "ar": "يُقاس قبل كل إصدار"},
    "qual.intro": {
        "en": "A change to the model, the prompt, the search or the library ships only after the same measures pass on cases it was never tuned on. Everything here is read from what was recorded; this page runs nothing.",
        "ar": "لا يُطلق أي تغيير في النموذج أو التعليمات أو البحث أو المكتبة إلا بعد أن تنجح المقاييس نفسها على حالات لم يُضبط عليها. كل ما هنا مقروء مما سُجِّل؛ ولا تشغّل هذه الصفحة شيئاً.",
    },
    "qual.now": {"en": "Now:", "ar": "الآن:"},
    "qual.prompts": {"en": "prompts", "ar": "التعليمات"},
    "qual.owner_view": {"en": "owner and quality lead view", "ar": "عرض المالك ومسؤول الجودة"},
    "qual.development": {"en": "Development cases passing", "ar": "الحالات التطويرية الناجحة"},
    "qual.not_recorded": {
        "en": "Not recorded yet: python scripts/verify_all.py --record",
        "ar": "لم يُسجَّل بعد: python scripts/verify_all.py --record",
    },
    "qual.held_out": {"en": "Held-out cases passing", "ar": "الحالات المحجوبة الناجحة"},
    "qual.held_out_not_run": {
        "en": "Not run yet: only when the owner asks, never tuned on",
        "ar": "لم تُشغَّل بعد: فقط عندما يطلب المالك، ولا يُضبط عليها",
    },
    "qual.covered": {"en": "Answer-key statements covered", "ar": "عبارات مفتاح الإجابة المغطاة"},
    "qual.covered_of": {"en": "{covered} of {expected}", "ar": "{covered} من {expected}"},
    "qual.not_measured": {
        "en": "Not measured yet: a recorded run with the AI (golden_cases --rag --record)",
        "ar": "لم يُقَس بعد: تشغيل مسجَّل مع الذكاء الاصطناعي (golden_cases --rag --record)",
    },
    "qual.removed": {"en": "Sentences removed by the quote check", "ar": "الجمل التي حذفها فحص الاقتباس"},
    "qual.removed_of": {
        "en": "{removed} of {all} AI items, in {cases} cases on this machine",
        "ar": "{removed} من {all} بنداً من الذكاء الاصطناعي، في {cases} حالة على هذا الجهاز",
    },
    "qual.wrong": {"en": "Specialists' marks: summary is wrong", "ar": "تقديرات المختصين: الملخص خاطئ"},
    "qual.wrong_of": {
        "en": "{wrong} of {marked} marked statements, in {decisions} decisions",
        "ar": "{wrong} من {marked} عبارة مقدَّرة، في {decisions} قراراً",
    },
    "qual.audit": {"en": "Audit log", "ar": "سجل التدقيق"},
    "qual.append_only": {"en": "Append-only", "ar": "يُضاف إليه فقط"},
    "qual.when": {"en": "When (UTC)", "ar": "متى (UTC)"},
    "qual.who": {"en": "Who", "ar": "مَن"},
    "qual.what": {"en": "What", "ar": "ماذا"},
    "qual.versions": {"en": "Versions", "ar": "الإصدارات"},
    "qual.who_not_recorded": {"en": "not recorded (no login yet)", "ar": "غير مسجَّل (لا تسجيل دخول بعد)"},
    "qual.prompt_v": {"en": "prompt", "ar": "التعليمات"},
    "qual.library_v": {"en": "library", "ar": "المكتبة"},
    "qual.no_events": {"en": "Nothing recorded yet.", "ar": "لم يُسجَّل شيء بعد."},
    "qual.gate": {"en": "Release gate", "ar": "بوابة الإصدار"},
    "qual.gate_note": {
        "en": "The owner records the sign-off and the Arabic check in data/quality/releases.csv; the results come from python scripts/verify_all.py --record.",
        "ar": "يسجّل المالك الموافقة ومراجعة العربية في data/quality/releases.csv؛ وتأتي النتائج من python scripts/verify_all.py --record.",
    },
    "audit.decision": {
        "en": "Decision: {decision}, case {case} ({domain})",
        "ar": "قرار: {decision}، الحالة {case} ({domain})",
    },
    "audit.design_choice": {
        "en": "Choice on a module page, case {case} ({domain})",
        "ar": "اختيار في صفحة وحدة، الحالة {case} ({domain})",
    },
    "audit.release_check": {"en": "Release check: every step passed", "ar": "فحص الإصدار: نجحت كل الخطوات"},
    "audit.release_check_failed": {"en": "Release check failed: {failed}", "ar": "فشل فحص الإصدار: {failed}"},
    "audit.golden_development": {
        "en": "Development cases: {passed} of {cases} passed ({mode})",
        "ar": "الحالات التطويرية: نجح {passed} من {cases} ({mode})",
    },
    "audit.golden_held_out": {
        "en": "Held-out cases: {passed} of {cases} passed ({mode})",
        "ar": "الحالات المحجوبة: نجح {passed} من {cases} ({mode})",
    },
    "audit.library": {"en": "Source library built: {n} passages", "ar": "بُنيت مكتبة المصادر: {n} مقطعاً"},
    "audit.rule_approved": {
        "en": "Clinic rule {rule} approved, version {version}",
        "ar": "اعتُمدت قاعدة العيادة {rule}، الإصدار {version}",
    },
    "audit.arabic_checked": {
        "en": "Arabic texts checked for release {release}",
        "ar": "رُوجعت النصوص العربية للإصدار {release}",
    },
    "audit.signed_off": {"en": "Release {release} signed off", "ar": "وُوفق على الإصدار {release}"},
    "run_mode.no_search": {"en": "without search", "ar": "دون بحث"},
    "run_mode.search": {"en": "with search", "ar": "مع البحث"},
    "run_mode.rag": {"en": "with search and the AI", "ar": "مع البحث والذكاء الاصطناعي"},
    "gate.tests": {"en": "All tests", "ar": "كل الاختبارات"},
    "gate.tests_pass": {"en": "{n} passed, {at}", "ar": "نجح {n}، {at}"},
    "gate.tests_fail": {"en": "Failed, {at}", "ar": "فشلت، {at}"},
    "gate.not_recorded": {
        "en": "Not recorded yet: python scripts/verify_all.py --record",
        "ar": "لم يُسجَّل بعد: python scripts/verify_all.py --record",
    },
    "gate.held_out": {"en": "Held-out cases", "ar": "الحالات المحجوبة"},
    "gate.held_out_result": {"en": "{passed} of {cases} passed, {at}", "ar": "نجح {passed} من {cases}، {at}"},
    "gate.arabic": {"en": "Arabic texts checked", "ar": "مراجعة النصوص العربية"},
    "gate.arabic_checked": {"en": "Checked by {by} on {on}", "ar": "راجعها {by} في {on}"},
    "gate.arabic_pending": {
        "en": "{n} texts awaiting an Arabic-reading specialist's check",
        "ar": "{n} نصاً بانتظار مراجعة مختص يقرأ العربية",
    },
    "gate.sign_off": {"en": "Owner's sign-off", "ar": "موافقة المالك"},
    "gate.signed_off": {
        "en": "Release {release} signed off by {by} on {on}",
        "ar": "وافق {by} على الإصدار {release} في {on}",
    },
    "gate.awaiting": {"en": "Awaiting the owner", "ar": "بانتظار المالك"},
    # ---- The knowledge layer pages (plan Part 5, 2026-10-25; knowledge/routes.py, knowledge/library.py) ----
    "part.knowledge": {"en": "Knowledge layer", "ar": "الطبقة المعرفية"},
    "kmod.sources": {"en": "1 Sources", "ar": "1 المصادر"},
    "kmod.evidence": {"en": "2 Evidence", "ar": "2 الأدلة"},
    "kmod.graph": {"en": "3 Graph and expertise", "ar": "3 المخطط المعرفي والخبرة"},
    "ksrc.title": {"en": "Source library and ingestion", "ar": "مكتبة المصادر وإدخالها"},
    "ksrc.kicker": {"en": "Knowledge 1", "ar": "المعرفة 1"},
    "ksrc.intro": {
        "en": "Only what is catalogued can be quoted. Every document keeps its licence as recorded and what extraction did to its text.",
        "ar": "لا يُقتبس إلا مما هو مُدرج في الفهرس. وتحتفظ كل وثيقة بترخيصها كما سُجِّل وبما فعله الاستخراج بنصها.",
    },
    "ksrc.kinds": {"en": "Kinds of source", "ar": "أنواع المصادر"},
    "ksrc.all": {"en": "All", "ar": "الكل"},
    "ksrc.documents": {"en": "Documents", "ar": "الوثائق"},
    "ksrc.search": {"en": "Search", "ar": "بحث"},
    "ksrc.search_hint": {"en": "Title, domain or licence", "ar": "العنوان أو المجال أو الترخيص"},
    "ksrc.search_button": {"en": "Show", "ar": "اعرض"},
    "ksrc.col_document": {"en": "Document", "ar": "الوثيقة"},
    "ksrc.col_kind": {"en": "Kind", "ar": "النوع"},
    "ksrc.col_language": {"en": "Language", "ar": "اللغة"},
    "ksrc.col_licence": {"en": "Licence", "ar": "الترخيص"},
    "ksrc.col_text": {"en": "Text", "ar": "النص"},
    "ksrc.col_status": {"en": "Status", "ar": "الحالة"},
    "ksrc.not_shown": {"en": "not shown", "ar": "غير مذكور"},
    "ksrc.no_text": {"en": "No extracted text", "ar": "لا نص مستخرَج"},
    "ksrc.pages": {"en": "{n} pages", "ar": "{n} صفحة"},
    "ksrc.references": {"en": "references from page {p} removed", "ar": "حُذفت المراجع من الصفحة {p}"},
    "ksrc.headers": {"en": "{n} repeated header lines removed", "ar": "حُذف {n} من أسطر الترويسة المكررة"},
    "ksrc.search_lines": {"en": "{n} search-syntax lines removed", "ar": "حُذف {n} من أسطر صيغ البحث"},
    "ksrc.split_words": {"en": "split words rejoined", "ar": "أُعيد وصل الكلمات المنقسمة"},
    "ksrc.thin_pages": {
        "en": "{n} pages with almost no text (figures, dividers or scans)",
        "ar": "{n} صفحة شبه خالية من النص (أشكال أو فواصل أو صور ممسوحة)",
    },
    "ksrc.text_ok": {"en": "text extracted", "ar": "استُخرج النص"},
    "kstatus.searched": {"en": "Searched", "ar": "يُبحث فيها"},
    "kstatus.not_in_index": {
        "en": "Catalogued, not in the search index",
        "ar": "مُدرجة في الفهرس، وليست في فهرس البحث",
    },
    "kstatus.link_only": {"en": "Link only: manual download needed", "ar": "رابط فقط: يلزم تنزيل يدوي"},
    "kstatus.not_catalogued": {"en": "Not catalogued: never quoted", "ar": "غير مُدرجة: لا يُقتبس منها"},
    "ksrc.passages": {"en": "{n} passages", "ar": "المقاطع: {n}"},
    "ksrc.not_in_gap_search": {"en": "left out of the gap search", "ar": "مستبعدة من البحث عن المعلومات الناقصة"},
    "ksrc.none_found": {"en": "No document matches.", "ar": "لا وثيقة مطابقة."},
    "ksrc.registry": {"en": "In the registry, not catalogued", "ar": "في السجل، وغير مُدرجة في الفهرس"},
    "ksrc.registry_note": {
        "en": "Downloaded or listed, but not in the catalog, so never searched or quoted (regulations and datasets are kept apart and not listed here).",
        "ar": "نُزّلت أو سُجّلت، لكنها ليست في الفهرس، فلا يُبحث فيها ولا يُقتبس منها (اللوائح ومجموعات البيانات محفوظة على حدة وغير مدرجة هنا).",
    },
    "ksrc.pipeline": {"en": "From document to search", "ar": "من الوثيقة إلى البحث"},
    "kstep.licence": {"en": "1 Licence check", "ar": "1 فحص الترخيص"},
    "kstep_does.licence": {"en": "recorded as printed, or \"not shown\"", "ar": "يُسجَّل كما هو مطبوع، أو «غير مذكور»"},
    "kstep.text": {"en": "2 Text out", "ar": "2 استخراج النص"},
    "kstep_does.text": {
        "en": "page by page; pages with almost no text counted",
        "ar": "صفحةً صفحة؛ وتُعدّ الصفحات شبه الخالية من النص",
    },
    "kstep.clean": {"en": "3 Clean", "ar": "3 التنظيف"},
    "kstep_does.clean": {
        "en": "headers, references, search syntax, split words",
        "ar": "الترويسات والمراجع وصيغ البحث والكلمات المنقسمة",
    },
    "kstep.passages": {"en": "4 Passages", "ar": "4 المقاطع"},
    "kstep_does.passages": {"en": "each with its page", "ar": "كلٌّ مع صفحته"},
    "kstep.index": {"en": "5 Local search index", "ar": "5 فهرس البحث المحلي"},
    "kstep_does.index": {"en": "multilingual, on this machine", "ar": "متعدد اللغات، على هذا الجهاز"},
    "ksrc.curator": {"en": "Needs a curator", "ar": "يحتاج إلى منسّق المصادر"},
    "ksrc.curator_none": {"en": "Nothing waiting.", "ar": "لا شيء بانتظار."},
    "curate.not_extracted": {
        "en": "{title}: no extracted text (python -m knowledge.ingest)",
        "ar": "{title}: لا نص مستخرَج (python -m knowledge.ingest)",
    },
    "curate.not_in_index": {
        "en": "{title}: catalogued, not in the search index (python -m knowledge.ingest)",
        "ar": "{title}: مُدرجة في الفهرس وليست في فهرس البحث (python -m knowledge.ingest)",
    },
    "curate.link_only": {
        "en": "{title}: download it by hand, then catalogue it",
        "ar": "{title}: نزّلها يدوياً ثم أدرجها في الفهرس",
    },
    "curate.search_quality_due": {
        "en": "Search-quality test due after the library build of {built} (python -m knowledge.evaluate --record)",
        "ar": "اختبار جودة البحث مستحق بعد بناء المكتبة في {built} (python -m knowledge.evaluate --record)",
    },
    "ksrc.last_search": {
        "en": "Last search-quality test: {at}, a right page in the top 5 for {hits} of {n}",
        "ar": "آخر اختبار لجودة البحث: {at}، صفحة صحيحة ضمن أول 5 في {hits} من {n}",
    },
    "ksrc.add": {"en": "Add a source", "ar": "أضف مصدراً"},
    "ksrc.add_how": {
        "en": "A curator downloads it (an open licence or a public work, never behind a paywall), lists it in data/knowledge/sources/catalog.json with its kind, language and licence as printed, then runs python -m knowledge.ingest and the search-quality test.",
        "ar": "ينزّلها منسّق المصادر (بترخيص مفتوح أو عمل عام، لا من خلف حاجز دفع)، ويدرجها في data/knowledge/sources/catalog.json مع نوعها ولغتها وترخيصها كما هو مطبوع، ثم يشغّل python -m knowledge.ingest واختبار جودة البحث.",
    },
    "kdomain.prosthetics": {"en": "Prosthetics", "ar": "الأطراف الاصطناعية"},
    "kdomain.orthotics": {"en": "Orthotics", "ar": "تقويم العظام"},
    "kdomain.gait": {"en": "Gait analysis", "ar": "تحليل المشية"},
    "kdomain.rehabilitation": {"en": "Rehabilitation", "ar": "إعادة التأهيل"},
    "kev.title": {"en": "Evidence and curation", "ar": "الأدلة والتنسيق"},
    "kev.kicker": {"en": "Knowledge 2", "ar": "المعرفة 2"},
    "kev.intro": {
        "en": "Each statement is the source's own words with its page. Its evidence fields come from the owner's rule table, which says which rule set them, or stay unassigned. Read-only here.",
        "ar": "كل عبارة هي كلمات المصدر نفسه مع صفحتها. وتأتي حقول الدليل فيها من جدول قواعد المالك، الذي يذكر القاعدة التي حدّدتها، أو تبقى غير محددة. للقراءة فقط هنا.",
    },
    "kev.reasons": {"en": "Why an item may need a curator", "ar": "لماذا قد يحتاج البند إلى منسّق"},
    "kev.all": {"en": "All", "ar": "الكل"},
    "kev.queue": {"en": "Knowledge items", "ar": "البنود المعرفية"},
    "kev.none": {"en": "No item.", "ar": "لا بند."},
    "kreason.no_rule": {"en": "No rule matched", "ar": "لم تنطبق أي قاعدة"},
    "kreason.layer_unassigned": {"en": "Layer unassigned", "ar": "الطبقة غير محددة"},
    "kreason.population_not_set": {"en": "Population not set", "ar": "الفئة غير محددة"},
    "kreason.practice": {"en": "Practice manual: no outcome evidence", "ar": "دليل ممارسة: بلا دليل على النتائج"},
    "kev.checked": {"en": "checked word for word against the page", "ar": "متحقَّق منه كلمةً كلمة مقابل الصفحة"},
    "kev.grade": {"en": "Grade, as printed", "ar": "الدرجة كما هي مطبوعة"},
    "kev.grade_note": {"en": "Copied from the source", "ar": "منسوخة من المصدر"},
    "kev.kind": {"en": "Kind of source", "ar": "نوع المصدر"},
    "kev.layer": {"en": "Evidence layer", "ar": "طبقة الدليل"},
    "kev.tag": {"en": "Evidence tag", "ar": "وسم الدليل"},
    "kev.confidence": {"en": "Confidence", "ar": "الثقة"},
    "kev.population": {"en": "Population", "ar": "الفئة"},
    "kev.limitations": {"en": "Limitations", "ar": "القيود"},
    "kev.unassigned": {"en": "Unassigned", "ar": "غير محددة"},
    "kev.set_by": {"en": "Set by the owner's rule {rule}", "ar": "حدّدتها قاعدة المالك {rule}"},
    "kev.no_rule": {"en": "No rule set it", "ar": "لم تحدّدها أي قاعدة"},
    "kev.not_set": {"en": "Not set", "ar": "غير محددة"},
    "kev.owners_value": {"en": "Only the owner's value", "ar": "قيمة المالك فقط"},
    "kev.read_only": {
        "en": "Read-only: the evidence fields are set only by the owner's rule table or values the owner gives (CLAUDE.md); a curator proposes a rule to the owner.",
        "ar": "للقراءة فقط: لا تُحدَّد حقول الدليل إلا بجدول قواعد المالك أو بقيم يعطيها المالك (CLAUDE.md)؛ ويقترح منسّق المصادر القاعدة على المالك.",
    },
    "kev.rules": {"en": "The owner's rule table", "ar": "جدول قواعد المالك"},
    "kev.rules_note": {"en": "Read-only here; only the owner edits it", "ar": "للقراءة فقط هنا؛ والمالك وحده يعدّله"},
    "kev.col_rule": {"en": "Rule", "ar": "القاعدة"},
    "kev.col_when": {"en": "When", "ar": "متى"},
    "kev.col_sets": {"en": "Sets (layer · tag · confidence)", "ar": "تحدّد (الطبقة · الوسم · الثقة)"},
    "kev.col_items": {"en": "Items", "ar": "البنود"},
    "kev.rules_values": {
        "en": "The rules and their values are the owner's words, shown as written (data/knowledge/evidence_rules.csv).",
        "ar": "القواعد وقيمها بكلمات المالك، معروضة كما كُتبت (data/knowledge/evidence_rules.csv).",
    },
    "kev.other_topic": {"en": "Other topic", "ar": "موضوع آخر"},
    "kvalidation.unreviewed": {"en": "Unreviewed", "ar": "غير مراجَع"},
    "kvalidation.rule-assigned": {"en": "Set by a rule", "ar": "حدّدته قاعدة"},
    "kvalidation.owner-reviewed": {"en": "Reviewed by the owner", "ar": "راجعه المالك"},
    "kvalidation.specialist-reviewed": {"en": "Reviewed by a specialist", "ar": "راجعه مختص"},
    "kgr.title": {"en": "Knowledge graph and expertise", "ar": "المخطط المعرفي والخبرة"},
    "kgr.kicker": {"en": "Knowledge 3", "ar": "المعرفة 3"},
    "kgr.intro": {
        "en": "The clinic's rules, the Arabic terms, and what the clinic itself will learn: what exists today, and what is not built yet.",
        "ar": "قواعد العيادة، والمصطلحات العربية، وما ستتعلمه العيادة نفسها: ما هو موجود اليوم، وما لم يُبنَ بعد.",
    },
    "kgr.rules": {"en": "Clinic rules", "ar": "قواعد العيادة"},
    "kgr.rules_note": {
        "en": "Each with its status, version, owner and approval date (data/knowledge/clinic_rules.csv)",
        "ar": "كلٌّ مع حالته وإصداره ومالكه وتاريخ اعتماده (data/knowledge/clinic_rules.csv)",
    },
    "kgr.col_rule": {"en": "Rule", "ar": "القاعدة"},
    "kgr.col_domain": {"en": "Domain", "ar": "المجال"},
    "kgr.col_status": {"en": "Status", "ar": "الحالة"},
    "kgr.col_source": {"en": "Where its wording comes from", "ar": "مصدر صياغتها"},
    "kgr.glossary": {"en": "Arabic terms", "ar": "المصطلحات العربية"},
    "kgr.glossary_now": {
        "en": "Every interface text, {n} in all, is in the Arabic term sheet ({sheet}) for an Arabic-reading specialist to check.",
        "ar": "كل نصوص الواجهة، وعددها {n}، في ورقة المصطلحات العربية ({sheet}) ليراجعها مختص يقرأ العربية.",
    },
    "kgr.glossary_later": {
        "en": "A glossary with a status per clinical term (checked, two terms in use, awaiting a check) is not built yet.",
        "ar": "لم يُبنَ بعد مسرد يذكر حالة كل مصطلح سريري (مراجَع، أو مصطلحان مستعملان، أو بانتظار المراجعة).",
    },
    "kgr.not_built": {"en": "Not built yet", "ar": "لم تُبنَ بعد"},
    "kgr_part.graph": {"en": "Design knowledge graph", "ar": "المخطط المعرفي للتصميم"},
    "kgr_does.graph": {
        "en": "problem → requirement → design feature → component or material → source, each link set by a curator and ending in a source",
        "ar": "المشكلة ← المتطلب ← خاصية التصميم ← المكوّن أو المادة ← المصدر، وكل رابط يضعه منسّق وينتهي بمصدر",
    },
    "kgr_part.cases": {"en": "Case library", "ar": "مكتبة الحالات"},
    "kgr_does.cases": {
        "en": "de-identified cases with the device chosen and how they went, shown as similar cases, never as an answer (use case 06)",
        "ar": "حالات مُزالة الهوية مع الجهاز المختار ومآلها، تُعرض كحالات مشابهة لا كإجابة (حالة الاستخدام 06)",
    },
    "kgr_part.data": {"en": "Structured data", "ar": "البيانات المنظمة"},
    "kgr_does.data": {
        "en": "component catalogues with weight limits, local stock and lead times, outcome-measure norms (today typed per case on modules 2–3)",
        "ar": "كتالوجات المكونات مع حدود الوزن والمخزون المحلي ومدد التوريد، ومعايير مقاييس النتائج (تُكتب اليوم لكل حالة في الوحدتين 2–3)",
    },
    "kgr.who_curates": {
        "en": "Who curates these, and how their entries are checked, is the owner's to decide.",
        "ar": "تحديد من ينسّق هذه وكيف تُراجع مدخلاتها متروك للمالك.",
    },
    "audit.search_quality": {
        "en": "Search quality: a right page in the top 5 for {hits} of {n}",
        "ar": "جودة البحث: صفحة صحيحة ضمن أول 5 في {hits} من {n}",
    },
    "audit.search_quality_orthotics": {
        "en": "Orthotic topic searches: a right passage for {hits} of {n}",
        "ar": "بحوث الموضوعات التقويمية: مقطع صحيح في {hits} من {n}",
    },
    # ---- The smart search page (plan Part 6, 2026-10-25; search/) ----
    "part.search": {"en": "Search and education", "ar": "البحث والتعليم"},
    "smod.search": {"en": "1 Smart search", "ar": "1 البحث الذكي"},
    "srch.title": {"en": "Smart search in the specialist library", "ar": "البحث الذكي في المكتبة المتخصصة"},
    "srch.kicker": {"en": "Use case 05", "ar": "حالة الاستخدام 05"},
    "srch.intro": {
        "en": "Ask in English or Arabic. Each answer sentence sits on the source's own words; when the library has nothing, the page says so and writes nothing in its place.",
        "ar": "اسأل بالإنجليزية أو بالعربية. تستند كل جملة في الإجابة إلى كلمات المصدر نفسه؛ وإذا لم يكن في المكتبة شيء، تقول الصفحة ذلك ولا تكتب شيئاً مكانه.",
    },
    "srch.marked": {"en": "Your mark is kept in the search log.", "ar": "حُفظ تقديرك في سجل البحث."},
    "srch.suggested": {"en": "Your suggestion is kept for the curator.", "ar": "حُفظ اقتراحك لمنسّق المصادر."},
    "srch.question": {"en": "Question", "ar": "السؤال"},
    "srch.placeholder": {
        "en": "e.g. suspension options when the limb's volume changes during the day",
        "ar": "مثلاً: خيارات التعليق عندما يتغيّر حجم الطرف خلال اليوم",
    },
    "srch.search": {"en": "Search", "ar": "ابحث"},
    "srch.both_languages": {
        "en": "Searched in English and Arabic sources",
        "ar": "يُبحث في المصادر الإنجليزية والعربية",
    },
    "srch.sources": {"en": "{n} catalogued sources", "ar": "المصادر المُدرجة: {n}"},
    "srch.local": {"en": "Search runs on this machine", "ar": "يجري البحث على هذا الجهاز"},
    "srch.filters": {"en": "Filters", "ar": "المرشّحات"},
    "srch.domain": {"en": "Domain", "ar": "المجال"},
    "srch.kind": {"en": "Kind of source", "ar": "نوع المصدر"},
    "srch.language": {"en": "Language", "ar": "اللغة"},
    "srch_lang.both": {"en": "Both", "ar": "كلتاهما"},
    "srch_lang.en": {"en": "English", "ar": "الإنجليزية"},
    "srch_lang.ar": {"en": "Arabic", "ar": "العربية"},
    "srch.from_year": {"en": "From year", "ar": "من سنة"},
    "srch.any_year": {"en": "Any", "ar": "أي سنة"},
    "srch.filters_note": {
        "en": "None ticked: every domain or kind. The evidence layer belongs to the knowledge items, not to passages, so it is no filter here.",
        "ar": "إن لم يُعلَّم شيء: كل المجالات أو الأنواع. وطبقة الدليل تخص البنود المعرفية لا المقاطع، فليست مرشّحاً هنا.",
    },
    "srch.apply": {"en": "Apply the filters", "ar": "طبّق المرشّحات"},
    "srch.what_sources_say": {"en": "What the sources say", "ar": "ما تقوله المصادر"},
    "srch.ai_count": {
        "en": "AI summary · {n} sentences, each quote checked",
        "ar": "ملخص بالذكاء الاصطناعي · {n} جمل، كل اقتباس متحقَّق منه",
    },
    "srch.order_note": {
        "en": "Options appear in the order the sources mention them. Nothing here is ranked or recommended.",
        "ar": "تظهر الخيارات بالترتيب الذي تذكرها به المصادر. لا شيء هنا مرتَّب أو موصى به.",
    },
    "srch.checked": {"en": "quote checked", "ar": "الاقتباس متحقَّق منه"},
    "srch.no_grade": {"en": "no grade printed", "ar": "لا درجة مطبوعة"},
    "srch.your_mark": {"en": "Your mark:", "ar": "تقديرك:"},
    "srch_mark.useful": {"en": "Useful", "ar": "مفيد"},
    "srch_mark.not_useful": {"en": "Not useful", "ar": "غير مفيد"},
    "srch_mark.summary_wrong": {"en": "A summary is wrong", "ar": "أحد الملخصات خاطئ"},
    "srch.ai_off": {
        "en": "No AI summary: a question is typed text, so it is not sent to the cloud model until the owner switches it on. The passages found are below.",
        "ar": "لا ملخص بالذكاء الاصطناعي: السؤال نص مكتوب، فلا يُرسل إلى النموذج السحابي حتى يشغّله المالك. والمقاطع التي وُجدت أدناه.",
    },
    "srch.ai_unavailable": {"en": "The AI could not answer:", "ar": "تعذّر على الذكاء الاصطناعي الإجابة:"},
    "srch.none_kept": {
        "en": "No AI sentence passed the checks; nothing is written in its place. The passages found are below.",
        "ar": "لم تجتز أي جملة من الذكاء الاصطناعي الفحوص؛ ولم يُكتب شيء مكانها. والمقاطع التي وُجدت أدناه.",
    },
    "srch.passages": {"en": "Passages found", "ar": "المقاطع التي وُجدت"},
    "srch.passages_count": {
        "en": "{n} passages from {docs} sources · order of match, not of quality",
        "ar": "{n} مقطعاً من {docs} مصادر · بترتيب التطابق لا الجودة",
    },
    "srch.page": {"en": "p. {p}", "ar": "ص {p}"},
    "srch.arabic_kept": {"en": "quoted in Arabic, never translated", "ar": "مقتبس بالعربية ولا يُترجم"},
    "srch.open_passage": {"en": "Open the passage", "ar": "افتح المقطع"},
    "srch.no_passages": {"en": "No passage found.", "ar": "لم يوجد مقطع."},
    "srch.start": {"en": "Type a question to search the library.", "ar": "اكتب سؤالاً للبحث في المكتبة."},
    "srch.no_answer_kicker": {"en": "When the library has no answer", "ar": "عندما لا تجيب المكتبة"},
    "srch.no_answer": {
        "en": "The library gave no answer to this question.",
        "ar": "لم تقدّم المكتبة إجابة عن هذا السؤال.",
    },
    "srch.nothing_written": {"en": "Nothing has been written in its place.", "ar": "ولم يُكتب شيء مكانها."},
    "srch.suggest_note": {"en": "What source would answer it (optional)", "ar": "ما المصدر الذي قد يجيب عنه (اختياري)"},
    "srch.suggest": {"en": "Suggest a source to the curator", "ar": "اقترح مصدراً على منسّق المصادر"},
    "srch.in_a_case": {"en": "Use it in a case", "ar": "استخدمه في حالة"},
    "srch.pin_later": {
        "en": "Pinning a passage to an open case, where it joins the case's review for the specialist to mark, comes in a later part.",
        "ar": "تثبيت مقطع في حالة مفتوحة، لينضم إلى مراجعتها فيقدّره المختص، يأتي في جزء لاحق.",
    },
    "srch.what_leaves": {"en": "What leaves this machine", "ar": "ما يغادر هذا الجهاز"},
    "srch.leaves_off": {
        "en": "Nothing: the AI summary is switched off, so the question stays here",
        "ar": "لا شيء: ملخص الذكاء الاصطناعي متوقف، فيبقى السؤال هنا",
    },
    "srch.leaves_on": {
        "en": "The question and the passages, to the one language model",
        "ar": "السؤال والمقاطع، إلى النموذج اللغوي الواحد",
    },
    "srch.never_notes": {"en": "Never a case's typed notes", "ar": "لا تُرسل أبداً ملاحظات حالة مكتوبة"},
    "srch.logged_no_who": {
        "en": "Searches are logged on this machine without who asked",
        "ar": "تُسجَّل عمليات البحث على هذا الجهاز دون ذكر من سأل",
    },
    "curate.suggested": {
        "en": "{n} sources suggested from searches (data/records/search_log.jsonl)",
        "ar": "اقتُرح {n} مصدراً من عمليات البحث (data/records/search_log.jsonl)",
    },
    "qual.searches": {
        "en": "Smart search: {n} searches, {answered} with AI sentences, {none} found no passage; marks: useful {useful}, not useful {not_useful}, a summary is wrong {wrong}; sources suggested {suggested}.",
        "ar": "البحث الذكي: {n} عملية بحث، منها {answered} بجمل من الذكاء الاصطناعي، و{none} لم تجد مقطعاً؛ التقديرات: مفيد {useful}، غير مفيد {not_useful}، أحد الملخصات خاطئ {wrong}؛ المصادر المقترحة {suggested}.",
    },
    # ---- Case-based learning (plan Part 7, 2026-10-25; search/learning_routes.py) ----
    "smod.learning": {"en": "2 Case-based learning", "ar": "2 التعلّم بالحالات"},
    "learn.title": {"en": "Case-based learning", "ar": "التعلّم بالحالات"},
    "learn.kicker": {"en": "Use case 06", "ar": "حالة الاستخدام 06"},
    "learn.intro": {
        "en": "Work an invented teaching case in five steps: read it, mark what is missing, write the options you would weigh and why, compare with the expert panel and with what the sources say, then reflect. Nothing is graded.",
        "ar": "اعمل على حالة تعليمية مُتخيَّلة في خمس خطوات: اقرأها، وحدّد ما ينقصها، واكتب الخيارات التي ستوازن بينها وأسبابك، ثم قارن بإجابات لجنة الخبراء وبما تقوله المصادر، ثم تأمّل. لا يُمنح أي تقدير.",
    },
    "learn.logged": {"en": "The case is in your learning log.", "ar": "أُضيفت الحالة إلى سجل التعلّم."},
    "learn.library": {"en": "Teaching cases", "ar": "الحالات التعليمية"},
    "learn.panel_recorded": {
        "en": "Panel answers v{v}, {n} members",
        "ar": "إجابات اللجنة، الإصدار {v}، عدد الأعضاء: {n}",
    },
    "learn.panel_not_recorded": {"en": "Panel answers not recorded yet", "ar": "لم تُسجَّل إجابات اللجنة بعد"},
    "learn.cpd_minutes": {"en": "{n} min", "ar": "{n} دقيقة"},
    "learn.start": {"en": "Start", "ar": "ابدأ"},
    "learn.no_cases": {
        "en": "No teaching cases yet (data/education/teaching_cases/).",
        "ar": "لا توجد حالات تعليمية بعد (data/education/teaching_cases/).",
    },
    "learn.library_note": {
        "en": "Teaching cases are invented, never copied from a record. Their level, CPD time, status and the expert panel's answers are the educator's to set; a draft is shown as a draft.",
        "ar": "الحالات التعليمية مُتخيَّلة ولا تُنسخ من أي سجل. مستواها ووقت التطوير المهني المستمر وحالتها وإجابات لجنة الخبراء يحدّدها المُدرِّب؛ وتظهر المسودة على أنها مسودة.",
    },
    "learn.my_log": {"en": "My learning log", "ar": "سجل التعلّم"},
    "learn.cases_worked": {"en": "Cases worked", "ar": "الحالات المُنجَزة"},
    "learn.cpd_hours": {"en": "CPD hours recorded", "ar": "ساعات التطوير المهني المسجّلة"},
    "learn.hours_note": {
        "en": "The time you recorded for each case, added up.",
        "ar": "مجموع الوقت الذي سجّلته لكل حالة.",
    },
    "learn.export": {"en": "Export the CPD record (CSV)", "ar": "تصدير سجل التطوير المهني (CSV)"},
    "learn.log_empty": {"en": "No cases worked yet.", "ar": "لم تُنجَز أي حالة بعد."},
    "learn.one_log": {
        "en": "One log for this machine until roles and login come.",
        "ar": "سجل واحد لهذا الجهاز إلى أن تُضاف الأدوار وتسجيل الدخول.",
    },
    "learn.none_reported": {"en": "none", "ar": "لا يوجد"},
    "learn_status.draft": {"en": "Draft, awaiting the educator", "ar": "مسودة بانتظار المُدرِّب"},
    "learn_status.approved": {"en": "Approved by the educator", "ar": "اعتمدها المُدرِّب"},
    "learn.level": {"en": "Level: {level}", "ar": "المستوى: {level}"},
    "learn.level_not_set": {"en": "Level not set yet", "ar": "لم يُحدَّد المستوى بعد"},
    "learn_level.foundation": {"en": "foundation", "ar": "تأسيسي"},
    "learn_level.intermediate": {"en": "intermediate", "ar": "متوسط"},
    "learn_level.advanced": {"en": "advanced", "ar": "متقدّم"},
    "learn.honest": {"en": "How learning stays honest", "ar": "كيف يبقى التعلّم أميناً"},
    "learn_honest.no_grade": {
        "en": "The tool never grades your clinical judgement: it shows where you and the panel differ.",
        "ar": "لا تُقيِّم الأداة حكمك السريري أبداً: تُظهر أين تختلف عن اللجنة.",
    },
    "learn_honest.panel_once": {
        "en": "The panel's answers are recorded once by the educator and versioned; your log keeps the version you compared with.",
        "ar": "يسجّل المُدرِّب إجابات اللجنة مرة واحدة بإصدارات مرقّمة؛ ويحفظ سجلك الإصدار الذي قارنت به.",
    },
    "learn_honest.invented": {
        "en": "Every teaching case is invented: fake data, no patient.",
        "ar": "كل حالة تعليمية مُتخيَّلة: بيانات وهمية، بلا مريض.",
    },
    "learn.steps": {"en": "Steps", "ar": "الخطوات"},
    "learn_step.read": {"en": "Read the case", "ar": "اقرأ الحالة"},
    "learn_step.missing": {"en": "What is missing?", "ar": "ما الذي ينقص؟"},
    "learn_step.options": {"en": "Options and why", "ar": "الخيارات وأسبابها"},
    "learn_step.compare": {"en": "Compare", "ar": "قارن"},
    "learn_step.reflect": {"en": "Reflect and log", "ar": "تأمّل وسجّل"},
    "learn.done": {"en": "done", "ar": "مُنجَزة"},
    "learn.the_case": {"en": "What the case records", "ar": "ما تسجّله الحالة"},
    "learn.read_note": {
        "en": "Only what is recorded is shown. Anything not listed was not recorded.",
        "ar": "يظهر ما سُجِّل فقط. وما لم يُدرَج لم يُسجَّل.",
    },
    "learn.next": {"en": "Next", "ar": "التالي"},
    "learn.missing_heading": {
        "en": "What information would you want before deciding?",
        "ar": "ما المعلومات التي تريدها قبل أن تقرّر؟",
    },
    "learn.missing_note": {
        "en": "Tick each item you would want recorded, or recorded more clearly.",
        "ar": "ضع علامة على كل بند تريد أن يُسجَّل، أو أن يُسجَّل بوضوح أكبر.",
    },
    "learn.other_missing": {"en": "Anything else, in your words", "ar": "أي شيء آخر، بكلماتك"},
    "learn.save_next": {"en": "Save and continue", "ar": "احفظ وتابع"},
    "learn.options_heading": {"en": "The options you would weigh, and why", "ar": "الخيارات التي ستوازن بينها، ولماذا"},
    "learn.options_note": {
        "en": "In your own words. This is your reasoning, not the tool's; nothing here is scored.",
        "ar": "بكلماتك. هذا تفكيرك لا تفكير الأداة؛ ولا يُقيَّم شيء هنا.",
    },
    "learn.options": {"en": "Options", "ar": "الخيارات"},
    "learn.reasons": {"en": "Why", "ar": "الأسباب"},
    "learn.save_compare": {"en": "Save and compare", "ar": "احفظ وقارن"},
    "learn.compare_missing": {
        "en": "What is missing: you, the panel and the sources",
        "ar": "ما ينقص: أنت واللجنة والمصادر",
    },
    "learn.found_of_panel": {
        "en": "You marked {n} of the {m} items the panel marked",
        "ar": "حدّدت {n} من البنود التي حدّدتها اللجنة وعددها {m}",
    },
    "learn.col_item": {"en": "Item", "ar": "البند"},
    "learn.col_you": {"en": "You", "ar": "أنت"},
    "learn.col_panel": {"en": "Panel", "ar": "اللجنة"},
    "learn.col_source": {"en": "Source", "ar": "المصدر"},
    "learn.you_missing": {"en": "Marked missing", "ar": "حدّدته ناقصاً"},
    "learn.you_not_marked": {"en": "Not marked", "ar": "لم تحدّده"},
    "learn.panel_none": {"en": "Not recorded yet", "ar": "لم يُسجَّل بعد"},
    "learn.panel_missing": {"en": "{n} of {m} marked it", "ar": "حدّده {n} من {m}"},
    "learn.panel_not_missing": {"en": "No member marked it", "ar": "لم يحدّده أي عضو"},
    "learn.no_source": {"en": "No source found in the library", "ar": "لم يُعثر على مصدر في المكتبة"},
    "learn.recorded_in_case": {"en": "Recorded in the case", "ar": "مسجّل في الحالة"},
    "learn.not_searched_item": {"en": "Not searched", "ar": "لم يُبحث عنه"},
    "learn.your_other": {"en": "You also wrote:", "ar": "وكتبت أيضاً:"},
    "learn.compare_note": {
        "en": "The source column is what the local search found for each item the case does not record; it says why an item matters, not what to decide.",
        "ar": "عمود المصدر هو ما وجده البحث المحلي لكل بند لا تسجّله الحالة؛ وهو يقول لماذا يهمّ البند، لا ما ينبغي أن تقرّره.",
    },
    "learn.compare_options": {"en": "Your options and the panel's reasoning", "ar": "خياراتك وتفكير اللجنة"},
    "learn.not_a_score": {"en": "Not a score", "ar": "ليس تقييماً"},
    "learn.your_reasoning": {"en": "Your reasoning", "ar": "تفكيرك"},
    "learn.reason_given": {"en": "Why:", "ar": "الأسباب:"},
    "learn.panel_reasoning": {"en": "The panel's reasoning", "ar": "تفكير اللجنة"},
    "learn.panel_words": {
        "en": "In the panel members' own words, version {v}, recorded {date}.",
        "ar": "بكلمات أعضاء اللجنة أنفسهم، الإصدار {v}، سُجِّل في {date}.",
    },
    "learn.panel_not_recorded_long": {
        "en": "The educator has not recorded the panel's answers for this case yet, so there is nothing to compare your options with yet.",
        "ar": "لم يسجّل المُدرِّب إجابات اللجنة لهذه الحالة بعد، فلا يوجد ما تُقارن به خياراتك حتى الآن.",
    },
    "learn.sources_on_missed": {
        "en": "What the sources say about an item you did not mark: {item}",
        "ar": "ما تقوله المصادر عن بند لم تحدّده: {item}",
    },
    "learn.to_reflect": {"en": "Continue to reflect", "ar": "تابع إلى التأمّل"},
    "learn.reflect_heading": {"en": "Reflect, then add the case to your log", "ar": "تأمّل، ثم أضف الحالة إلى سجلك"},
    "learn.reflection": {
        "en": "What would you do differently next time?",
        "ar": "ما الذي ستفعله بشكل مختلف في المرة القادمة؟",
    },
    "learn.minutes": {"en": "Minutes spent (for your CPD record)", "ar": "الدقائق المستغرقة (لسجل التطوير المهني)"},
    "learn.save_log": {"en": "Add to my learning log", "ar": "أضف إلى سجل التعلّم"},
    "learn.ask_later": {
        "en": "Asking the educator a question comes with roles and login.",
        "ar": "سؤال المُدرِّب يأتي مع الأدوار وتسجيل الدخول.",
    },
    "learn.back_library": {"en": "Back to the teaching cases", "ar": "العودة إلى الحالات التعليمية"},
    "error.learn_too_long": {
        "en": "Each text can be at most {n} characters.",
        "ar": "يمكن أن يصل كل نص إلى {n} حرفاً كحدٍّ أقصى.",
    },
    "error.learn_options_needed": {
        "en": "Write the options you would weigh before comparing.",
        "ar": "اكتب الخيارات التي ستوازن بينها قبل المقارنة.",
    },
    "error.learn_compare_first": {
        "en": "Look at the comparison before adding the case to your log.",
        "ar": "اطّلع على المقارنة قبل إضافة الحالة إلى سجلك.",
    },
    "error.learn_minutes": {
        "en": "Minutes must be a whole number from 1 to {n}, or left empty.",
        "ar": "يجب أن تكون الدقائق عدداً صحيحاً من 1 إلى {n}، أو تُترك فارغة.",
    },
    "learn_unit.kg": {"en": "{n} kg", "ar": "{n} كغ"},
    "learn_unit.years": {"en": "{n} years", "ar": "{n} سنة"},
    "learn_unit.months": {"en": "{n} months", "ar": "{n} شهر"},
    "learn_unit.deg": {"en": "{n}°", "ar": "{n}°"},
    "learn_unit.m_s": {"en": "{n} m/s", "ar": "{n} م/ث"},
    # ---- Patient record and governance (plan Part 8, 2026-10-27; record/) ----
    "part.record": {"en": "Patient record", "ar": "سجل المريض"},
    "recmod.record": {"en": "1 Record and follow-up", "ar": "1 السجل والمتابعة"},
    "recmod.governance": {"en": "2 Consent and governance", "ar": "2 الموافقة والحوكمة"},
    "rec.title_list": {"en": "Patient records", "ar": "سجلات المرضى"},
    "rec.kicker": {"en": "Use case 07", "ar": "حالة الاستخدام 07"},
    "rec.intro": {
        "en": "One record per person across domains, under a code only. The name, birth date and file number stay in the clinic's own system.",
        "ar": "سجل واحد لكل شخص عبر المجالات، برمز فقط. يبقى الاسم وتاريخ الميلاد ورقم الملف في نظام العيادة نفسه.",
    },
    "rec.records": {"en": "Records on this machine", "ar": "السجلات على هذا الجهاز"},
    "rec.new": {"en": "Open a new record", "ar": "افتح سجلاً جديداً"},
    "rec.col_code": {"en": "Code", "ar": "الرمز"},
    "rec.col_opened": {"en": "Opened", "ar": "تاريخ الفتح"},
    "rec.col_cases": {"en": "Cases", "ar": "الحالات"},
    "rec.deletion_open_short": {"en": "deletion requested", "ar": "طُلب الحذف"},
    "rec.no_cases_short": {"en": "no case yet", "ar": "لا توجد حالة بعد"},
    "rec.none_yet": {
        "en": "No record yet. Open one, record the person's consent, then attach cases at their intake.",
        "ar": "لا يوجد سجل بعد. افتح سجلاً، وسجّل موافقة الشخص، ثم أرفق الحالات عند إدخالها.",
    },
    "rec.how": {"en": "How the record works", "ar": "كيف يعمل السجل"},
    "rec_how.code": {
        "en": "The app makes a code for each person. Keep the link between the code and the person's name in the clinic's own system.",
        "ar": "ينشئ التطبيق رمزاً لكل شخص. احتفظ بالربط بين الرمز واسم الشخص في نظام العيادة نفسه.",
    },
    "rec_how.consent_first": {
        "en": "Record the consent first: a case can be attached only once the person agrees to a care record.",
        "ar": "سجّل الموافقة أولاً: لا يمكن إرفاق حالة إلا بعد موافقة الشخص على سجل الرعاية.",
    },
    "rec_how.attach": {
        "en": "A case is attached at its intake: enter the code in the form's \"Person code\" field.",
        "ar": "تُرفق الحالة عند إدخالها: أدخل الرمز في حقل \"رمز الشخص\" في النموذج.",
    },
    "rec_how.never_sent": {
        "en": "Notes and the record itself are never sent to a language model. A case goes to the cloud model only if the person agreed.",
        "ar": "لا تُرسل الملاحظات ولا السجل نفسه إلى أي نموذج لغوي أبداً. ولا تُرسل الحالة إلى النموذج السحابي إلا إذا وافق الشخص.",
    },
    "rec_how.no_sign_in": {
        "en": "There is no sign-in yet: whoever uses this machine can open every record, and the access trail cannot say who.",
        "ar": "لا يوجد تسجيل دخول بعد: يستطيع كل من يستخدم هذا الجهاز فتح كل السجلات، ولا يستطيع سجل الاطلاع أن يحدّد من فعل ذلك.",
    },
    "rec.to_governance": {"en": "Consent and governance", "ar": "الموافقة والحوكمة"},
    "rec.title_record": {"en": "One record across domains, with follow-up", "ar": "سجل واحد عبر المجالات، مع المتابعة"},
    "rec.record_intro": {
        "en": "Every case, review, design choice, version and visit for one person, in time order, so the next specialist starts from what was done and why.",
        "ar": "كل حالة ومراجعة واختيار تصميم وإصدار وزيارة لشخص واحد، بترتيبها الزمني، ليبدأ الأخصائي التالي مما أُنجز ولماذا.",
    },
    "rec.person": {"en": "Person {code}", "ar": "الشخص {code}"},
    "rec.code_only": {
        "en": "Record code only: the name and file number stay in the clinic's own system",
        "ar": "رمز السجل فقط: يبقى الاسم ورقم الملف في نظام العيادة نفسه",
    },
    "rec.fake_data": {"en": "Test record · fake data", "ar": "سجل تجريبي · بيانات وهمية"},
    "rec.team_decides": {"en": "The care team decides", "ar": "فريق الرعاية هو من يقرّر"},
    "rec.note_saved": {"en": "The note is added to the record.", "ar": "أُضيفت الملاحظة إلى السجل."},
    "rec.deletion_open": {
        "en": "A deletion was requested on {date} ({by}). The owner removes the content by hand and keeps this line; until then no case can be attached.",
        "ar": "طُلب الحذف في {date} ({by}). يزيل المالك المحتوى يدوياً ويُبقي هذا السطر؛ وحتى ذلك الحين لا يمكن إرفاق أي حالة.",
    },
    "rec.cases": {"en": "Cases", "ar": "الحالات"},
    "rec.latest_choice": {"en": "Latest design choice", "ar": "آخر اختيار للتصميم"},
    "rec.open": {"en": "Open", "ar": "افتح"},
    "rec.none_recorded": {"en": "None recorded", "ar": "لم يُسجَّل شيء"},
    "rec.follow_up": {"en": "Next review", "ar": "المراجعة التالية"},
    "rec.due_on": {"en": "Due {date}", "ar": "موعدها {date}"},
    "rec.due_no_date": {"en": "Due, no date set", "ar": "مستحقة، بلا تاريخ"},
    "rec.date_passed": {"en": "date has passed", "ar": "فات موعدها"},
    "rec.none_due": {"en": "None due", "ar": "لا شيء مستحق"},
    "rec.consent": {"en": "Consent", "ar": "الموافقة"},
    "rec.see_consent": {"en": "See all consent", "ar": "اطّلع على كل الموافقات"},
    "rec.timeline": {"en": "Timeline", "ar": "التسلسل الزمني"},
    "rec.filter": {"en": "Show one domain", "ar": "اعرض مجالاً واحداً"},
    "rec.all": {"en": "All", "ar": "الكل"},
    "rec.reason": {"en": "Reason:", "ar": "السبب:"},
    "rec.no_events": {"en": "Nothing dated recorded yet.", "ar": "لم يُسجَّل شيء مؤرَّخ بعد."},
    "rec.no_cases": {
        "en": "No case attached yet. A case is attached at its intake: enter {code} in its \"Person code\" field.",
        "ar": "لم تُرفق أي حالة بعد. تُرفق الحالة عند إدخالها: أدخل {code} في حقل \"رمز الشخص\".",
    },
    "rec.new_case": {"en": "New {domain} case", "ar": "حالة جديدة: {domain}"},
    "rec.case_missing": {
        "en": "Case {id} is attached but its file is not on this machine.",
        "ar": "الحالة {id} مرفقة لكن ملفها غير موجود على هذا الجهاز.",
    },
    "rec.measures": {"en": "Outcome measures", "ar": "مقاييس النتائج"},
    "rec.measures_by": {"en": "As the clinician entered them", "ar": "كما أدخلها الأخصائي"},
    "rec.measure": {"en": "Measure", "ar": "المقياس"},
    "rec.no_measures": {
        "en": "No outcome measure entered yet (each domain's follow-up page).",
        "ar": "لم يُدخل أي مقياس للنتائج بعد (صفحة المتابعة في كل مجال).",
    },
    "rec.measures_note": {
        "en": "Each value is shown as entered, with how it was measured and when; who measured it is not recorded until sign-in. The tool draws no conclusion from a change.",
        "ar": "تُعرض كل قيمة كما أُدخلت، مع طريقة قياسها وتاريخه؛ ولا يُسجَّل من قاسها إلى أن يُضاف تسجيل الدخول. لا تستخلص الأداة أي استنتاج من التغيّر.",
    },
    "rec.schedule": {"en": "Follow-up schedule", "ar": "جدول المتابعة"},
    "rec.no_visits": {"en": "No visit recorded yet.", "ar": "لم تُسجَّل أي زيارة بعد."},
    "rec.schedule_note": {
        "en": "Visits as recorded on each domain's follow-up page. Intervals and reminders come from a versioned clinic rule, which the owner has not set yet; no reminder is sent to anyone.",
        "ar": "الزيارات كما سُجّلت في صفحة المتابعة لكل مجال. تأتي الفترات والتذكيرات من قاعدة عيادة ذات إصدارات لم يحدّدها المالك بعد؛ ولا يُرسل أي تذكير لأحد.",
    },
    "rec.alerts": {"en": "Open alerts", "ar": "تنبيهات مفتوحة"},
    "rec.notes": {"en": "Hand-over notes", "ar": "ملاحظات التسليم"},
    "rec.notes_note": {
        "en": "Written by one team member for the next. They stay on this machine and are never sent to a language model. A note is added, never changed.",
        "ar": "يكتبها عضو في الفريق للعضو التالي. تبقى على هذا الجهاز ولا تُرسل إلى أي نموذج لغوي أبداً. تُضاف الملاحظة ولا تُعدَّل.",
    },
    "rec.note": {"en": "New note", "ar": "ملاحظة جديدة"},
    "rec.add_note": {"en": "Add to the record", "ar": "أضف إلى السجل"},
    "rec.not_recorded": {"en": "not recorded", "ar": "غير مسجّلة"},
    "rec.none": {"en": "none", "ar": "لا يوجد"},
    "rec_ev.intake": {"en": "Case recorded at intake", "ar": "سُجّلت الحالة عند الإدخال"},
    "rec_ev.review": {"en": "Review signed: {decision}", "ar": "وُقّعت المراجعة: {decision}"},
    "rec_ev.choice": {"en": "Design choice recorded", "ar": "سُجّل اختيار التصميم"},
    "rec_ev.visit": {"en": "Follow-up visit, {status}", "ar": "زيارة متابعة، {status}"},
    "rec_ev.socket_version": {"en": "Socket version {n}", "ar": "إصدار التجويف {n}"},
    "rec_ev.alignment_version": {"en": "Alignment version {n}", "ar": "إصدار المحاذاة {n}"},
    "rec_ev.parameter_version": {"en": "Design parameters, version {n}", "ar": "معايير التصميم، الإصدار {n}"},
    "consent.care_record": {"en": "Keep a care record", "ar": "الاحتفاظ بسجل رعاية"},
    "consent.cloud_model": {
        "en": "Send coded fields to the cloud language model",
        "ar": "إرسال الحقول المرمّزة إلى النموذج اللغوي السحابي",
    },
    "consent.quality_use": {"en": "De-identified use for quality measures", "ar": "الاستخدام دون هوية لقياسات الجودة"},
    "consent.teaching_use": {"en": "Use as the basis of a teaching case", "ar": "الاستخدام أساساً لحالة تعليمية"},
    "consent_does.care_record": {
        "en": "Needed to use the tool for this person: their cases are kept under this code.",
        "ar": "لازمة لاستخدام الأداة لهذا الشخص: تُحفظ حالاته تحت هذا الرمز.",
    },
    "consent_does.cloud_model": {
        "en": "Only the level, side and recorded K-level of a case (an orthotic case: condition, side and months since onset), never typed notes. Without it, the case is shown with its sources but no AI summaries.",
        "ar": "فقط مستوى البتر والجهة ومستوى K المسجّل للحالة (وفي حالة الجبيرة: الحالة والجهة والأشهر منذ البداية)، ولا تُرسل الملاحظات المكتوبة أبداً. ومن دونها تُعرض الحالة مع مصادرها بلا ملخصات بالذكاء الاصطناعي.",
    },
    "consent_does.quality_use": {
        "en": "Counts and marks only, never the record. Without it, this person's reviews are left out of the quality counts.",
        "ar": "أعداد وتقديرات فقط، ولا يُستخدم السجل أبداً. ومن دونها تُستبعد مراجعات هذا الشخص من أعداد الجودة.",
    },
    "consent_does.teaching_use": {
        "en": "A teaching case would be rewritten so no one can be recognised. The teaching cases here are invented, so none is made from a record.",
        "ar": "تُعاد كتابة الحالة التعليمية بحيث لا يمكن التعرّف على أحد. الحالات التعليمية هنا مُتخيَّلة، فلا تُصنع أي حالة من سجل.",
    },
    "consent_short.care_record": {"en": "Care record", "ar": "سجل الرعاية"},
    "consent_short.cloud_model": {"en": "Cloud model", "ar": "النموذج السحابي"},
    "consent_short.quality_use": {"en": "Quality use", "ar": "الاستخدام للجودة"},
    "consent_short.teaching_use": {"en": "Teaching use", "ar": "الاستخدام للتعليم"},
    "consent_answer.agreed": {"en": "Agreed", "ar": "موافَق عليه"},
    "consent_answer.declined": {"en": "Declined", "ar": "مرفوض"},
    "consent_answer.withdrawn": {"en": "Withdrawn", "ar": "مسحوب"},
    "consent_do.agreed": {"en": "Record agreed", "ar": "سجّل الموافقة"},
    "consent_do.declined": {"en": "Record declined", "ar": "سجّل الرفض"},
    "consent_do.withdrawn": {"en": "Withdraw", "ar": "اسحب الموافقة"},
    "gov.title": {"en": "Consent, access and data governance", "ar": "الموافقة والوصول وحوكمة البيانات"},
    "gov.kicker": {"en": "Privacy by design", "ar": "الخصوصية في التصميم"},
    "gov.intro": {
        "en": "What the person agreed to, what leaves this machine, who may see what, and the trail of every look.",
        "ar": "ما وافق عليه الشخص، وما يغادر هذا الجهاز، ومن يحق له رؤية ماذا، وسجل كل اطلاع.",
    },
    "gov.created": {
        "en": "Record {code} is open. Record the person's consent below, then attach cases at their intake with this code.",
        "ar": "فُتح السجل {code}. سجّل موافقة الشخص أدناه، ثم أرفق الحالات عند إدخالها بهذا الرمز.",
    },
    "gov.saved": {"en": "Saved as a new line in the record.", "ar": "حُفظ سطراً جديداً في السجل."},
    "gov.consent": {"en": "Consent", "ar": "الموافقة"},
    "gov.consent_lang": {"en": "Consent text shown in:", "ar": "يُعرض نص الموافقة بـ:"},
    "gov.consent_note": {
        "en": "Each item is separate and can be withdrawn. A change is a new line in the record; the old one stays.",
        "ar": "كل بند مستقل ويمكن سحبه. أي تغيير سطر جديد في السجل، ويبقى السطر القديم.",
    },
    "gov.shown_in": {"en": "shown in {language}", "ar": "لغة العرض: {language}"},
    "gov.consent_history": {"en": "Every consent line ({n})", "ar": "كل أسطر الموافقة ({n})"},
    "gov.consent_draft": {
        "en": "This consent wording is a draft awaiting the owner; the clinic's own consent form is the one that counts.",
        "ar": "صياغة الموافقة هذه مسودة بانتظار المالك؛ ونموذج الموافقة الخاص بالعيادة هو المعتمد.",
    },
    "gov.open_person": {
        "en": "Open a person's record to see and record their consent, their access trail and their requests.",
        "ar": "افتح سجل شخص لترى موافقته وتسجّلها، ولترى سجل الاطلاع وطلباته.",
    },
    "gov.to_records": {"en": "Patient records", "ar": "سجلات المرضى"},
    "gov.where": {"en": "Where each piece of data goes", "ar": "أين تذهب كل بيانات"},
    "gov.where_from": {
        "en": "Read from the settings the code follows",
        "ar": "مقروء من الإعدادات التي يتبعها البرنامج",
    },
    "gov.col_data": {"en": "Data", "ar": "البيانات"},
    "gov.col_here": {"en": "This machine", "ar": "هذا الجهاز"},
    "gov.col_cloud": {"en": "Cloud language model", "ar": "النموذج اللغوي السحابي"},
    "gov.col_quality": {"en": "Quality reports", "ar": "تقارير الجودة"},
    "gov_data.identifiers": {"en": "Name, birth date, file number", "ar": "الاسم وتاريخ الميلاد ورقم الملف"},
    "gov_data.coded": {"en": "Coded case fields", "ar": "حقول الحالة المرمّزة"},
    "gov_data.typed": {"en": "Typed notes and hand-over notes", "ar": "الملاحظات المكتوبة وملاحظات التسليم"},
    "gov_data.recordings": {"en": "Gait recordings and scans", "ar": "تسجيلات المشي والمسوحات"},
    "gov_data.marks": {"en": "Specialists' marks", "ar": "تقديرات الأخصائيين"},
    "gov.never_clinic": {"en": "Never: the clinic's system only", "ar": "أبداً: في نظام العيادة فقط"},
    "gov.never": {"en": "Never", "ar": "أبداً"},
    "gov.kept": {"en": "Kept", "ar": "تُحفظ"},
    "gov.not_collected": {"en": "Not collected by this app", "ar": "لا يجمعها هذا التطبيق"},
    "gov.counts_consent": {"en": "Counts only, with the person's consent", "ar": "أعداد فقط، بموافقة الشخص"},
    "gov_cloud.on": {"en": "{what}: on, only with the person's consent", "ar": "{what}: مفعّل، بموافقة الشخص فقط"},
    "gov_cloud.search_on": {"en": "{what}: on", "ar": "{what}: مفعّل"},
    "gov_cloud.off": {"en": "{what}: off", "ar": "{what}: متوقف"},
    "gov.search_questions": {"en": "Search questions", "ar": "أسئلة البحث"},
    "gov.provider": {
        "en": "Language model in use: {provider}. Only the coded fields and the passages found go out.",
        "ar": "النموذج اللغوي المستخدم: {provider}. لا يخرج سوى الحقول المرمّزة والمقاطع التي وُجدت.",
    },
    "gov.where_note": {
        "en": "Nothing else leaves this machine. The search runs here.",
        "ar": "لا يغادر هذا الجهاز أي شيء آخر. ويجري البحث هنا.",
    },
    "gov.roles": {"en": "Who may see what", "ar": "من يحق له رؤية ماذا"},
    "gov.roles_from": {
        "en": "The owner's table (data/governance/roles.csv)",
        "ar": "جدول المالك (data/governance/roles.csv)",
    },
    "gov.col_role": {"en": "Role", "ar": "الدور"},
    "gov_col.record": {"en": "Record", "ar": "السجل"},
    "gov_col.notes": {"en": "Notes", "ar": "الملاحظات"},
    "gov_col.sign": {"en": "Sign", "ar": "التوقيع"},
    "gov_col.export": {"en": "Export", "ar": "التصدير"},
    "gov.col_status": {"en": "Status", "ar": "الحالة"},
    "gov.not_set": {"en": "not set", "ar": "غير محدّد"},
    "gov.draft": {"en": "draft, awaiting the owner", "ar": "مسودة بانتظار المالك"},
    "gov.approved": {"en": "approved by {owner}, {date}", "ar": "اعتمده {owner} في {date}"},
    "gov.no_roles": {"en": "No role set yet.", "ar": "لم يُحدَّد أي دور بعد."},
    "gov.not_enforced": {
        "en": "Not enforced yet: there is no sign-in, so every page is open to whoever uses this machine.",
        "ar": "غير مطبَّق بعد: لا يوجد تسجيل دخول، فكل الصفحات متاحة لكل من يستخدم هذا الجهاز.",
    },
    "role.treating_specialist": {"en": "Treating prosthetist or orthotist", "ar": "أخصائي الأطراف أو الجبائر المعالج"},
    "role.therapist": {"en": "Physiotherapist or occupational therapist", "ar": "أخصائي العلاج الطبيعي أو الوظيفي"},
    "role.rehab_physician": {"en": "Rehabilitation physician", "ar": "طبيب التأهيل"},
    "role.gait_lab": {"en": "Gait lab", "ar": "مختبر المشي"},
    "role.learner_educator": {"en": "Learner or educator", "ar": "المتعلّم أو المُدرِّب"},
    "role.curator": {"en": "Curator", "ar": "منسّق المصادر"},
    "role.owner_quality": {"en": "Owner and quality lead", "ar": "المالك ومسؤول الجودة"},
    "access.yes": {"en": "Yes", "ar": "نعم"},
    "access.no": {"en": "No", "ar": "لا"},
    "access.sessions_only": {"en": "Sessions only", "ar": "الجلسات فقط"},
    "access.counts_only": {"en": "Counts only", "ar": "الأعداد فقط"},
    "access.own_domain": {"en": "Own domain", "ar": "مجاله فقط"},
    "access.rehabilitation": {"en": "Rehabilitation", "ar": "التأهيل"},
    "access.medical_review": {"en": "Medical review", "ar": "المراجعة الطبية"},
    "access.gait_reports": {"en": "Gait reports", "ar": "تقارير المشي"},
    "access.rules_and_releases": {"en": "Rules and releases", "ar": "القواعد والإصدارات"},
    "access.with_reason": {"en": "With a reason", "ar": "مع ذكر السبب"},
    "access.reports": {"en": "Reports", "ar": "التقارير"},
    "gov.trail": {"en": "Access trail", "ar": "سجل الاطلاع"},
    "access_action.created": {"en": "Record opened", "ar": "فُتح السجل"},
    "access_action.opened_record": {"en": "Looked at the record", "ar": "اطُّلع على السجل"},
    "access_action.opened_governance": {"en": "Looked at consent and governance", "ar": "اطُّلع على الموافقة والحوكمة"},
    "access_action.opened_copy": {"en": "Looked at the copy", "ar": "اطُّلع على النسخة"},
    "access_action.consent": {"en": "Consent recorded", "ar": "سُجّلت الموافقة"},
    "access_action.attached_case": {"en": "Case attached", "ar": "أُرفقت حالة"},
    "access_action.added_note": {"en": "Note added", "ar": "أُضيفت ملاحظة"},
    "access_action.copy_given": {"en": "Copy given", "ar": "سُلّمت نسخة"},
    "access_action.deletion_requested": {"en": "Deletion requested", "ar": "طُلب الحذف"},
    "gov.trail_more": {
        "en": "{n} earlier lines are in the person's copy.",
        "ar": "توجد أسطر أقدم عددها {n} في نسخة الشخص.",
    },
    "gov.trail_note": {
        "en": "Only ever added to. Who did each thing is not recorded until sign-in. The person can ask for this list: it is part of their copy.",
        "ar": "يُضاف إليه فقط. ولا يُسجَّل من فعل كل شيء إلى أن يُضاف تسجيل الدخول. ويحق للشخص طلب هذه القائمة: فهي جزء من نسخته.",
    },
    "gov.retention": {"en": "Retention and requests", "ar": "الاحتفاظ والطلبات"},
    "gov_setting.retention_period": {"en": "Kept for", "ar": "مدة الاحتفاظ"},
    "gov_setting.law": {"en": "Law it follows", "ar": "القانون المتّبع"},
    "gov.requests": {"en": "Requests", "ar": "الطلبات"},
    "gov.no_requests": {"en": "No request yet.", "ar": "لا توجد طلبات بعد."},
    "request_kind.copy": {"en": "Copy given", "ar": "سُلّمت نسخة"},
    "request_kind.deletion": {"en": "Deletion requested", "ar": "طُلب الحذف"},
    "requested_by.person": {"en": "on the person's request", "ar": "بطلب من الشخص"},
    "requested_by.representative": {"en": "on their representative's request", "ar": "بطلب من ممثّله"},
    "requested_by.clinic": {"en": "on the clinic's request", "ar": "بطلب من العيادة"},
    "gov.give_copy": {"en": "Give the person a copy", "ar": "سلّم الشخص نسخة"},
    "gov.on_whose_request": {"en": "On whose request", "ar": "بطلب ممن"},
    "gov.record_deletion": {"en": "Record a deletion request", "ar": "سجّل طلب حذف"},
    "gov.deletion_note": {
        "en": "A deletion removes the content and keeps a line saying when and on whose request. The owner does the deletion by hand (README, \"Patient record\").",
        "ar": "يزيل الحذف المحتوى ويُبقي سطراً يذكر متى تم وبطلب ممن. ويتولى المالك الحذف يدوياً (README، \"Patient record\").",
    },
    "copy.title": {"en": "Copy of record {code}", "ar": "نسخة من السجل {code}"},
    "copy.intro": {
        "en": "Everything this app holds about the person: the cases as recorded, the timeline, the measures, the notes, every consent line, the requests and the access trail.",
        "ar": "كل ما يحفظه هذا التطبيق عن الشخص: الحالات كما سُجّلت، والتسلسل الزمني، والمقاييس، والملاحظات، وكل أسطر الموافقة، والطلبات، وسجل الاطلاع.",
    },
    "copy.back": {"en": "Back to consent and governance", "ar": "العودة إلى الموافقة والحوكمة"},
    "copy.print": {"en": "Print it from the browser to hand it over.", "ar": "اطبعها من المتصفح لتسليمها."},
    "copy.cases": {"en": "Cases as recorded", "ar": "الحالات كما سُجّلت"},
    "copy.no_notes": {"en": "No note.", "ar": "لا توجد ملاحظات."},
    "copy.who_not_recorded": {"en": "who: not recorded", "ar": "من: غير مسجّل"},
    "intake.person": {"en": "Patient record (optional)", "ar": "سجل المريض (اختياري)"},
    "intake.person_code": {"en": "Person code", "ar": "رمز الشخص"},
    "intake.person_hint": {
        "en": "Attach this case to a person's record. Leave empty for a case on its own. Never a name or file number.",
        "ar": "أرفق هذه الحالة بسجل شخص. اتركه فارغاً لحالة مستقلة. لا تكتب اسماً أو رقم ملف أبداً.",
    },
    "intake.person_open": {"en": "Patient records", "ar": "سجلات المرضى"},
    "qual.left_out": {
        "en": "{n} review(s) left out: the person did not agree to quality use.",
        "ar": "استُبعدت مراجعات عددها {n}: لم يوافق الشخص على الاستخدام للجودة.",
    },
    "error.consent_same": {
        "en": "That is already the consent recorded for this item.",
        "ar": "هذه هي الموافقة المسجّلة لهذا البند بالفعل.",
    },
    "error.consent_withdraw_unagreed": {
        "en": "Only an agreed item can be withdrawn.",
        "ar": "لا يمكن سحب إلا بند موافَق عليه.",
    },
    "error.note_empty": {"en": "Write the note first.", "ar": "اكتب الملاحظة أولاً."},
    "error.note_too_long": {
        "en": "A note can be at most {n} characters.",
        "ar": "يمكن أن تصل الملاحظة إلى {n} حرفاً كحدٍّ أقصى.",
    },
    "error.person_unknown": {
        "en": "No record has the code {code}. Open the record first (Patient record), or leave the field empty.",
        "ar": "لا يوجد سجل بالرمز {code}. افتح السجل أولاً (سجل المريض)، أو اترك الحقل فارغاً.",
    },
    "error.person_no_care_record": {
        "en": "Record {code} has no agreed consent to keep a care record, so no case can be attached.",
        "ar": "لا توجد للسجل {code} موافقة على الاحتفاظ بسجل رعاية، فلا يمكن إرفاق أي حالة.",
    },
    "error.person_deletion_open": {
        "en": "A deletion was requested for record {code}, so no case can be attached.",
        "ar": "طُلب حذف السجل {code}، فلا يمكن إرفاق أي حالة.",
    },
    "rec.deleted": {
        "en": "The content of this record was deleted on {date}. The request and this line stay.",
        "ar": "حُذف محتوى هذا السجل في {date}. ويبقى الطلب وهذا السطر.",
    },
    "rec.deleted_short": {"en": "content deleted", "ar": "حُذف المحتوى"},
    # ---- Rehabilitation (plan Part 9, 2026-10-27; rehabilitation/) ----
    "part.rehabilitation": {"en": "Rehabilitation", "ar": "التأهيل"},
    "rehmod.plan": {"en": "1 Plan", "ar": "1 الخطة"},
    "rehmod.progress": {"en": "2 Progress", "ar": "2 التقدّم"},
    "rehmod.training": {"en": "3 Training with the device", "ar": "3 التدريب مع الجهاز"},
    "rehmod.team": {"en": "4 Team record", "ar": "4 سجل الفريق"},
    "rehmod.needs_case": {"en": "Open a case first (Rehabilitation)", "ar": "افتح حالة أولاً (التأهيل)"},
    "rehmod.therapist_decides": {
        "en": "Decision support: the therapist decides",
        "ar": "دعم القرار: المعالج هو من يقرّر",
    },
    "rehmod.team_decides": {"en": "Decision support: the team decides", "ar": "دعم القرار: الفريق هو من يقرّر"},
    "mod.save": {"en": "Save", "ar": "احفظ"},
    "rehab.title": {"en": "Rehabilitation", "ar": "التأهيل"},
    "rehab.kicker": {
        "en": "Rehabilitation, from the plan to the team's record",
        "ar": "التأهيل، من الخطة إلى سجل الفريق",
    },
    "rehab.intro": {
        "en": "Rehabilitation works on a prosthetic or orthotic case: the goals agreed with the person, the interventions, progress, training with the device and the team's record. Every value is the team's.",
        "ar": "يعمل التأهيل على حالة أطراف اصطناعية أو تقويم: الأهداف المتفق عليها مع الشخص، والتدخلات، والتقدّم، والتدريب مع الجهاز، وسجل الفريق. كل قيمة يحدّدها الفريق.",
    },
    "rehab.cases": {"en": "Cases on this machine", "ar": "الحالات على هذا الجهاز"},
    "rehab.has_plan": {"en": "has a rehabilitation plan", "ar": "لها خطة تأهيل"},
    "rehab.open": {"en": "Open the plan", "ar": "افتح الخطة"},
    "rehab.start": {"en": "Start a plan", "ar": "ابدأ خطة"},
    "rehab.no_cases": {
        "en": "No case yet. Rehabilitation works on a case: enter one first.",
        "ar": "لا توجد حالة بعد. يعمل التأهيل على حالة: أدخل حالة أولاً.",
    },
    "rehab.modules": {"en": "The four modules", "ar": "الوحدات الأربع"},
    "rehab_does.plan": {
        "en": "goals agreed with the person, interventions with what the sources say, phases and the team",
        "ar": "أهداف متفق عليها مع الشخص، وتدخلات مع ما تقوله المصادر، ومراحل، والفريق",
    },
    "rehab_does.progress": {"en": "measures over time and goal attainment", "ar": "المقاييس عبر الزمن وتحقيق الأهداف"},
    "rehab_does.training": {
        "en": "tasks tied to the device's requirements, the home programme",
        "ar": "مهام مرتبطة بمتطلبات الجهاز، وبرنامج التمارين المنزلية",
    },
    "rehab_does.team": {
        "en": "one timeline for the team, the handover, next steps",
        "ar": "تسلسل زمني واحد للفريق، وملخص التسليم، والخطوات التالية",
    },
    "rehab.honest": {"en": "What the tool does here", "ar": "ما تفعله الأداة هنا"},
    "rehab_honest.team_values": {
        "en": "Goals, doses, scores and tasks are the team's; the tool writes, scores and ranks nothing.",
        "ar": "الأهداف والجرعات والدرجات والمهام يحدّدها الفريق؛ ولا تكتب الأداة شيئاً ولا تقيّمه ولا ترتّبه.",
    },
    "rehab_honest.sources": {
        "en": "Next to each kind of intervention: what the library says, quoted as printed with its page; the therapist's own intervention has no source.",
        "ar": "بجانب كل نوع من التدخلات: ما تقوله المكتبة، مقتبساً كما طُبع مع صفحته؛ ولا مصدر للتدخل الذي يضعه المعالج بنفسه.",
    },
    "rehab_honest.no_ai": {
        "en": "Nothing of a rehabilitation plan is sent to a language model; the handover is written by a person.",
        "ar": "لا يُرسل شيء من خطة التأهيل إلى أي نموذج لغوي؛ ويكتب ملخص التسليم شخص.",
    },
    "rehab_honest.drafts": {
        "en": "The lists of interventions, roles and task statuses are Claude's draft, awaiting the owner and a therapist.",
        "ar": "قوائم التدخلات والأدوار وحالات المهام مسودة من Claude بانتظار المالك ومعالج.",
    },
    "rehab.card": {"en": "Rehabilitation", "ar": "التأهيل"},
    "rehab.card_none": {
        "en": "Nothing seen in training is waiting for you.",
        "ar": "لا توجد ملاحظات من التدريب بانتظارك.",
    },
    "rehab.card_no_plan": {
        "en": "No rehabilitation plan for this case yet.",
        "ar": "لا توجد خطة تأهيل لهذه الحالة بعد.",
    },
    "rehab.card_open": {"en": "Rehabilitation: training with the device", "ar": "التأهيل: التدريب مع الجهاز"},
    "rplan.title": {"en": "Rehabilitation plan", "ar": "خطة التأهيل"},
    "rplan.intro": {
        "en": "Goals the person agreed to, then interventions with what the sources say about each. The therapist sets every dose.",
        "ar": "الأهداف التي وافق عليها الشخص، ثم التدخلات مع ما تقوله المصادر عن كل منها. يحدّد المعالج كل جرعة.",
    },
    "rplan.goals": {"en": "Goals", "ar": "الأهداف"},
    "rplan.agreed": {"en": "Agreed with the person on {date}", "ar": "اتُّفق عليها مع الشخص في {date}"},
    "rplan.not_agreed": {"en": "Not yet agreed with the person", "ar": "لم يُتفق عليها مع الشخص بعد"},
    "rplan.review_every_is": {"en": "review every {every}", "ar": "المراجعة كل {every}"},
    "rplan.within_is": {"en": "within {within}", "ar": "خلال {within}"},
    "rplan.scaled": {"en": "Scaled −2 to +2", "ar": "مقياس من −2 إلى +2"},
    "rplan.review_on_is": {"en": "review on {date}", "ar": "المراجعة في {date}"},
    "rplan.no_goals": {"en": "No goal yet.", "ar": "لا توجد أهداف بعد."},
    "rplan.agreed_on": {"en": "Agreed with the person on", "ar": "تاريخ الاتفاق مع الشخص"},
    "rplan.review_every": {"en": "Review every", "ar": "المراجعة كل"},
    "rplan.goals_edit": {"en": "Add or change goals", "ar": "أضف أهدافاً أو عدّلها"},
    "rplan.level": {"en": "ICF level", "ar": "مستوى ICF"},
    "rplan.goal": {"en": "Goal, in the words agreed", "ar": "الهدف، بالكلمات المتفق عليها"},
    "rplan.within": {"en": "Within", "ar": "خلال"},
    "rplan.review_on": {"en": "Review on", "ar": "المراجعة في"},
    "rplan.goals_note": {
        "en": "Each goal is scaled −2 to +2 with the person; the levels of the scale are theirs. Emptying a goal removes it.",
        "ar": "يُقاس كل هدف من −2 إلى +2 مع الشخص؛ ومستويات المقياس يحدّدونها هم. إفراغ الهدف يحذفه.",
    },
    "rplan.save_goals": {"en": "Save the goals", "ar": "احفظ الأهداف"},
    "rplan.interventions": {"en": "Interventions", "ar": "التدخلات"},
    "rplan.dose_by": {"en": "Dose set by the therapist", "ar": "يحدّد المعالج الجرعة"},
    "rplan.intervention": {"en": "Intervention", "ar": "التدخل"},
    "rplan.for_goals": {"en": "For goals", "ar": "للأهداف"},
    "rplan.dose": {"en": "Dose", "ar": "الجرعة"},
    "rplan.sources_say": {"en": "What the sources say", "ar": "ما تقوله المصادر"},
    "rplan.no_dose": {"en": "not set", "ar": "غير محدّدة"},
    "rplan.own": {"en": "No source in the library: the therapist's own.", "ar": "لا مصدر في المكتبة: من وضع المعالج."},
    "rplan.no_source": {
        "en": "No source in the library on this kind of intervention.",
        "ar": "لا يوجد مصدر في المكتبة عن هذا النوع من التدخلات.",
    },
    "rplan.not_searched": {"en": "The library could not be searched.", "ar": "تعذّر البحث في المكتبة."},
    "rplan.sources_note": {
        "en": "Found by the local search for each kind of intervention, quoted as printed with its page: not summarised and not checked to support this case. The therapist reads and judges.",
        "ar": "وجدها البحث المحلي لكل نوع من التدخلات، مقتبسة كما طُبعت مع صفحتها: دون تلخيص ودون تحقق من أنها تدعم هذه الحالة. يقرأ المعالج ويحكم.",
    },
    "rplan.no_interventions": {"en": "No intervention yet.", "ar": "لا توجد تدخلات بعد."},
    "rplan.interventions_edit": {"en": "Add or change interventions", "ar": "أضف تدخلات أو عدّلها"},
    "rplan.kind": {"en": "Kind", "ar": "النوع"},
    "rplan.intervention_name": {"en": "In the therapist's words", "ar": "بكلمات المعالج"},
    "rplan.interventions_note": {
        "en": "\"The therapist's own\" needs its name and is never searched. Emptying a row removes it.",
        "ar": "\"من وضع المعالج\" يحتاج إلى اسم ولا يُبحث عنه أبداً. إفراغ الصف يحذفه.",
    },
    "rplan.save_interventions": {"en": "Save the interventions", "ar": "احفظ التدخلات"},
    "rplan.phases": {"en": "Phases", "ar": "المراحل"},
    "rplan.phase_status": {"en": "Status", "ar": "الحالة"},
    "rplan.phase_when": {"en": "When", "ar": "متى"},
    "rplan.team": {"en": "The team", "ar": "الفريق"},
    "rplan.team_edit": {"en": "Add or change the team", "ar": "أضف أعضاء الفريق أو عدّلهم"},
    "rplan.role": {"en": "Role", "ar": "الدور"},
    "rplan.does": {"en": "Does", "ar": "يتولّى"},
    "rplan.to_progress": {"en": "See progress", "ar": "اطّلع على التقدّم"},
    "rprog.title": {"en": "Progress", "ar": "التقدّم"},
    "rprog.intro": {
        "en": "Measures as recorded at each session. The therapist judges the change: the tool computes none.",
        "ar": "المقاييس كما سُجّلت في كل جلسة. يحكم المعالج على التغيّر: ولا تحسب الأداة أي تغيّر.",
    },
    "rprog.smallest_change": {
        "en": "The smallest change that matters for each measure is the owner's, copied from its source with its page; not set yet.",
        "ar": "أصغر تغيّر ذي معنى لكل مقياس يحدّده المالك، منقولاً من مصدره مع صفحته؛ ولم يُحدَّد بعد.",
    },
    "rprog.attainment": {"en": "Goal attainment", "ar": "تحقيق الأهداف"},
    "rprog.scored_by": {"en": "Scored by the therapist with the person", "ar": "يقيّمه المعالج مع الشخص"},
    "rprog.not_scored": {"en": "not scored yet", "ar": "لم يُقيَّم بعد"},
    "rprog.goal": {"en": "Goal", "ar": "الهدف"},
    "rprog.score": {"en": "Score", "ar": "الدرجة"},
    "rprog.scored_on": {"en": "Scored on", "ar": "تاريخ التقييم"},
    "rprog.note": {"en": "Note", "ar": "ملاحظة"},
    "rprog.add_score": {"en": "Add the score", "ar": "أضف الدرجة"},
    "rprog.scores_note": {"en": "Each score is added, never changed.", "ar": "تُضاف كل درجة ولا تُعدَّل."},
    "rprog.no_goals": {"en": "Set the goals in the plan first:", "ar": "حدّد الأهداف في الخطة أولاً:"},
    "rprog.rule_alerts": {
        "en": "Alerts from clinic rules (for example a measure flat for three weeks) wait for the owner's rules; these alerts are the therapist's own.",
        "ar": "التنبيهات المستندة إلى قواعد العيادة (مثل ثبات مقياس ثلاثة أسابيع) تنتظر قواعد المالك؛ وهذه التنبيهات من وضع المعالج.",
    },
    "rprog.to_training": {"en": "Training with the device", "ar": "التدريب مع الجهاز"},
    "fu.back_to.plan": {"en": "Change the plan →", "ar": "عدّل الخطة ←"},
    "fu.back_to.training": {"en": "Change the training →", "ar": "عدّل التدريب ←"},
    "rtrain.title": {"en": "Training with the device", "ar": "التدريب مع الجهاز"},
    "rtrain.intro": {
        "en": "Training tied to what the device was built to do: each task names the requirement or goal it trains.",
        "ar": "تدريب مرتبط بما صُنع الجهاز لأجله: تذكر كل مهمة المتطلب أو الهدف الذي تدرّبه.",
    },
    "rtrain.tasks": {"en": "Training tasks", "ar": "مهام التدريب"},
    "rtrain.from_requirements": {
        "en": "From the device's requirements ({domain}) and the goals",
        "ar": "من متطلبات الجهاز ({domain}) والأهداف",
    },
    "rtrain.no_requirements": {
        "en": "The device's requirements ({domain}) are not written yet; a task can name a goal.",
        "ar": "لم تُكتب متطلبات الجهاز ({domain}) بعد؛ ويمكن أن تذكر المهمة هدفاً.",
    },
    "rtrain.task": {"en": "Task", "ar": "المهمة"},
    "rtrain.trains": {"en": "Trains", "ar": "تدرّب"},
    "rtrain.stage": {"en": "Stage", "ar": "المرحلة"},
    "rtrain.status": {"en": "Status", "ar": "الحالة"},
    "rtrain.no_tasks": {"en": "No task yet.", "ar": "لا توجد مهام بعد."},
    "rtrain.tasks_edit": {"en": "Add or change tasks", "ar": "أضف مهام أو عدّلها"},
    "rtrain.save_tasks": {"en": "Save the tasks", "ar": "احفظ المهام"},
    "rtrain.home": {"en": "Home programme", "ar": "برنامج التمارين المنزلية"},
    "rtrain.home_ar": {"en": "In Arabic", "ar": "بالعربية"},
    "rtrain.home_en": {"en": "In English", "ar": "بالإنجليزية"},
    "rtrain.checked_by": {
        "en": "Arabic checked by (an Arabic-reading therapist)",
        "ar": "راجع العربية (معالج يقرأ العربية)",
    },
    "rtrain.home_note": {
        "en": "Written by the therapist. The person receives it only once an Arabic-reading therapist has checked the Arabic.",
        "ar": "يكتبه المعالج. ولا يتسلّمه الشخص إلا بعد أن يراجع معالج يقرأ العربية النص العربي.",
    },
    "rtrain.save_home": {"en": "Save the home programme", "ar": "احفظ برنامج التمارين المنزلية"},
    "rtrain.home_empty": {"en": "No home programme written yet.", "ar": "لم يُكتب برنامج التمارين المنزلية بعد."},
    "rtrain.seen_heading": {
        "en": "Seen in training, for the device specialist",
        "ar": "ما لوحظ في التدريب، لأخصائي الجهاز",
    },
    "rtrain.for": {"en": "for the {role}", "ar": "إلى {role}"},
    "rtrain.answered": {"en": "Answered on {date}:", "ar": "رُدّ عليه في {date}:"},
    "rtrain.answer": {"en": "The specialist's answer", "ar": "ردّ الأخصائي"},
    "rtrain.save_answer": {"en": "Save the answer", "ar": "احفظ الرد"},
    "rtrain.none_seen": {"en": "Nothing sent yet.", "ar": "لم يُرسل شيء بعد."},
    "rtrain.seen": {"en": "What was seen", "ar": "ما لوحظ"},
    "rtrain.for_whom": {"en": "For", "ar": "إلى"},
    "rtrain.send": {"en": "Send to their list", "ar": "أرسل إلى قائمته"},
    "rtrain.seen_note": {
        "en": "Shown on the case's follow-up page for the specialist. Added, never changed; no video clip reaches the app.",
        "ar": "يظهر للأخصائي في صفحة متابعة الحالة. يُضاف ولا يُعدَّل؛ ولا يصل أي مقطع فيديو إلى التطبيق.",
    },
    "rtrain.to_team": {"en": "Team record", "ar": "سجل الفريق"},
    "rteam.title": {"en": "Follow-up information for the team", "ar": "معلومات المتابعة للفريق"},
    "rteam.intro": {
        "en": "One place for what each professional recorded, the next steps and the summary for a handover.",
        "ar": "مكان واحد لما سجّله كل أخصائي، والخطوات التالية، وملخص التسليم.",
    },
    "rteam.timeline": {"en": "Timeline", "ar": "التسلسل الزمني"},
    "rteam.from_record": {"en": "from the record", "ar": "من السجل"},
    "rteam.session": {"en": "Session", "ar": "جلسة"},
    "rteam.nothing_yet": {"en": "Nothing recorded yet.", "ar": "لم يُسجَّل شيء بعد."},
    "rteam.add_entry": {"en": "Add an entry", "ar": "أضف مُدخلاً"},
    "rteam.on": {"en": "Date", "ar": "التاريخ"},
    "rteam.kind": {"en": "Kind", "ar": "النوع"},
    "rteam.entry": {"en": "What was done or seen", "ar": "ما أُنجز أو لوحظ"},
    "rteam.entry_note": {"en": "An entry is added, never changed.", "ar": "يُضاف المُدخل ولا يُعدَّل."},
    "rteam.save_entry": {"en": "Add to the team record", "ar": "أضف إلى سجل الفريق"},
    "rteam.handover": {"en": "Handover summary", "ar": "ملخص التسليم"},
    "rteam.no_handover": {"en": "none yet", "ar": "لا يوجد بعد"},
    "rteam.signed": {"en": "signed by the {role}, {date}", "ar": "وقّعه {role} في {date}"},
    "rteam.not_signed": {"en": "version {n}, not yet signed", "ar": "الإصدار {n}، لم يُوقَّع بعد"},
    "rteam.written_by": {
        "en": "Written by the {role} on {date} (version {n}).",
        "ar": "كتبه {role} في {date} (الإصدار {n}).",
    },
    "rteam.signed_by": {"en": "Signed by", "ar": "يوقّعه"},
    "rteam.sign": {"en": "Sign", "ar": "وقّع"},
    "rteam.write_handover": {"en": "Write the handover", "ar": "اكتب ملخص التسليم"},
    "rteam.new_version": {"en": "Write a new version", "ar": "اكتب إصداراً جديداً"},
    "rteam.handover_text": {"en": "Handover, from the record above", "ar": "ملخص التسليم، من السجل أعلاه"},
    "rteam.written_by_label": {"en": "Written by", "ar": "كتبه"},
    "rteam.save_handover": {"en": "Save as a new version", "ar": "احفظ إصداراً جديداً"},
    "rteam.handover_note": {
        "en": "Written and signed by a person, never drafted by a language model (the owner's open decision). Sending it is done outside the tool.",
        "ar": "يكتبه ويوقّعه شخص، ولا يصوغه نموذج لغوي أبداً (قرار مفتوح للمالك). ويتم إرساله خارج الأداة.",
    },
    "rteam.next_steps": {"en": "Next steps", "ar": "الخطوات التالية"},
    "rteam.step": {"en": "Step", "ar": "الخطوة"},
    "rteam.step_on": {"en": "On", "ar": "في"},
    "rteam.done": {"en": "done", "ar": "أُنجزت"},
    "intervention.gait_training": {"en": "Gait training", "ar": "التدريب على المشي"},
    "intervention.balance_training": {"en": "Balance training", "ar": "التدريب على التوازن"},
    "intervention.strength_training": {"en": "Strength training", "ar": "تمارين التقوية"},
    "intervention.treadmill_training": {"en": "Treadmill training", "ar": "التدريب على جهاز المشي"},
    "intervention.device_use": {
        "en": "Putting on, taking off and caring for the device",
        "ar": "ارتداء الجهاز ونزعه والعناية به",
    },
    "intervention.task_practice": {
        "en": "Task practice: daily activities",
        "ar": "التدريب على المهام: الأنشطة اليومية",
    },
    "intervention.limb_care": {"en": "Residual limb care", "ar": "العناية بالطرف المتبقي"},
    "intervention.mirror_therapy": {"en": "Mirror therapy", "ar": "العلاج بالمرآة"},
    "intervention.home_programme": {"en": "Home programme", "ar": "برنامج التمارين المنزلية"},
    "intervention.falls_prevention": {"en": "Falls prevention", "ar": "الوقاية من السقوط"},
    "intervention.other": {"en": "The therapist's own", "ar": "من وضع المعالج"},
    "rphase.inpatient": {"en": "Inpatient", "ar": "داخل المستشفى"},
    "rphase.outpatient": {"en": "Outpatient", "ar": "العيادات الخارجية"},
    "rphase.community": {"en": "Community", "ar": "في المجتمع"},
    "phase_status.not_started": {"en": "not started", "ar": "لم تبدأ"},
    "phase_status.current": {"en": "now", "ar": "الحالية"},
    "phase_status.done": {"en": "done", "ar": "انتهت"},
    "role_rehab.physiotherapist": {"en": "physiotherapist", "ar": "أخصائي العلاج الطبيعي"},
    "role_rehab.occupational_therapist": {"en": "occupational therapist", "ar": "أخصائي العلاج الوظيفي"},
    "role_rehab.prosthetist": {"en": "prosthetist", "ar": "أخصائي الأطراف الاصطناعية"},
    "role_rehab.orthotist": {"en": "orthotist", "ar": "أخصائي الجبائر والتقويم"},
    "role_rehab.rehab_physician": {"en": "rehabilitation physician", "ar": "طبيب التأهيل"},
    "role_rehab.nurse": {"en": "nurse", "ar": "الممرض"},
    "role_rehab.psychologist": {"en": "psychologist", "ar": "الأخصائي النفسي"},
    "role_rehab.other": {"en": "other team member", "ar": "عضو آخر في الفريق"},
    "task_status.not_started": {"en": "Not started", "ar": "لم تبدأ"},
    "task_status.with_help": {"en": "With help", "ar": "بالمساعدة"},
    "task_status.with_cues": {"en": "With cues", "ar": "بالتوجيه"},
    "task_status.independent": {"en": "Independent", "ar": "مستقل"},
    "entry_kind.therapy": {"en": "Therapy", "ar": "العلاج"},
    "entry_kind.device": {"en": "Device", "ar": "الجهاز"},
    "entry_kind.medical": {"en": "Medical", "ar": "طبي"},
    "rec_ev.rehab_plan": {"en": "Rehabilitation goals agreed", "ar": "اتُّفق على أهداف التأهيل"},
    "rec_ev.rehab_score": {"en": "Goal {goal} scored {score}", "ar": "قُيّم الهدف {goal} بدرجة {score}"},
    "rec_ev.team_entry": {"en": "Team record: the {role}", "ar": "سجل الفريق: {role}"},
    "rec_ev.handover": {
        "en": "Handover version {n} signed by the {role}",
        "ar": "وقّع {role} الإصدار {n} من ملخص التسليم",
    },
    "error.goal_needs_level": {"en": "Choose each goal's ICF level.", "ar": "اختر مستوى ICF لكل هدف."},
    "error.intervention_needs_kind": {"en": "Choose each intervention's kind.", "ar": "اختر نوع كل تدخل."},
    "error.intervention_other_needs_name": {
        "en": "Name the therapist's own intervention.",
        "ar": "اكتب اسم التدخل الذي يضعه المعالج.",
    },
    "error.team_needs_role": {"en": "Choose each team member's role.", "ar": "اختر دور كل عضو في الفريق."},
    "error.score_needed": {"en": "Choose a score from −2 to +2.", "ar": "اختر درجة من −2 إلى +2."},
    "error.score_date_needed": {"en": "Give the date of the score.", "ar": "أدخل تاريخ الدرجة."},
    "error.observation_incomplete": {
        "en": "Write what was seen and choose who it is for.",
        "ar": "اكتب ما لوحظ واختر لمن يُرسل.",
    },
    "error.answer_needed": {"en": "Write the answer.", "ar": "اكتب الرد."},
    "error.entry_incomplete": {
        "en": "An entry needs its date, role, kind and words.",
        "ar": "يحتاج المُدخل إلى تاريخه ودوره ونوعه ونصه.",
    },
    "error.handover_incomplete": {
        "en": "Write the handover and choose who wrote it.",
        "ar": "اكتب ملخص التسليم واختر من كتبه.",
    },
    "error.nothing_to_sign": {
        "en": "There is no unsigned handover to sign.",
        "ar": "لا يوجد ملخص تسليم غير موقَّع لتوقيعه.",
    },
    "rtrain.not_checked": {
        "en": "The Arabic text has not been checked by an Arabic-reading therapist yet: don't give it to the person.",
        "ar": "لم يراجع معالج يقرأ العربية النص العربي بعد: لا تعطه للشخص.",
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
