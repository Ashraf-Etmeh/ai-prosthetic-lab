"""The prosthetic RAG: the instructions for the AI, what it is told about the case, and the page's sections.

Same pipeline and checks for every domain (reasoning/rag.py): the search finds
passages per topic (prosthetics/topics.py), the writer answers each part as
JSON, and every item's quote is checked word for word against its passage
before it is shown. Only what differs lives here: the instructions (worded for
a prosthetics specialist), the case facts the writer may see, and how the kept
items become the review page's sections.

IMPORTANT: the instructions forbid advice; the model reports what the sources
say for the case. The specialist decides.
"""

import json

from prosthetics.case import Case
from prosthetics.component_guide import COMPONENTS
from prosthetics.component_support import recorded_k_level
from prosthetics.fitting_guide import READINESS_FIELDS, SECTIONS
from prosthetics.topics import COMPONENTS_PART, FITTING, PARTS
from reasoning.models import FUNCTIONAL_LEVEL, ComponentSection, ComponentSupport, FittingSupport, FunctionalLevel
from reasoning.rag import FAITHFULNESS, GRADE_PHRASES, Generation, Profile, statements_for, terms_line
from reasoning.rag_topics import GAPS
from shared.case_schema import recorded_value
from shared.config import MAX_ITEMS_PER_TOPIC, PROMPT_VERSION

# The Arabic terms of the review page (shared/i18n.py), so the AI's Arabic sentences use the
# page's word for each thing, every time (the first live run gave socket as التجويف and
# المقبس, transtibial as تحت الركبة and عبر القصبة, fitting as التركيب and التثبيت).
# reasoning/tests/test_rag.py checks that each is the page's own wording.
ARABIC_TERMS = (
    ("prosthesis", "الطرف الاصطناعي"),
    ("residual limb", "الطرف المتبقي"),
    ("amputation", "البتر"),
    ("socket", "التجويف"),
    ("interface", "الواجهة"),
    ("liner", "البطانة"),
    ("suspension", "نظام التعليق"),
    ("knee unit", "وحدة الركبة"),
    ("foot and ankle", "القدم والكاحل"),
    ("pylon", "الأنبوب الواصل"),
    ("alignment", "المحاذاة"),
    ("fitting", "التركيب"),
    ("readiness for fitting", "الجاهزية للتركيب"),
    ("preparatory (interim) prosthesis", "طرف اصطناعي تمهيدي (مؤقت)"),
    ("definitive", "نهائي"),
    ("functional level, K-level", "المستوى الوظيفي"),
    ("transtibial, TT", "تحت الركبة"),
    ("transfemoral, TF", "فوق الركبة"),
    ("knee disarticulation", "فصل مفصل الركبة"),
    ("transradial", "تحت المرفق"),
    ("transhumeral", "فوق المرفق"),
    ("phantom pain", "ألم شبحي"),
)


SYSTEM_PROMPT = f"""\
You help a prosthetics specialist review one fictional amputation case. You receive the case's amputation \
level, side and recorded functional level, a list of topics, and passages that a search found in the \
specialist's source library (guidelines, manuals and reviews). For each topic, you report in short sentences what the passages say that bears on this \
case. The specialist reads each sentence next to the quote that backs it, and decides.

Rules:
1. Use only the passages given. Add nothing from outside them.
2. Each item backs one sentence with one quote. Copy the quote exactly, character for character, from the \
passage named by passage_id: one continuous stretch of text of at least five words, usually one or two whole \
sentences. Do not shorten it, join separate pieces, leave words out, add "...", fix typing errors or translate \
it. Code compares every quote with its passage and deletes any item whose quote is not found there.
3. sentence_en is one short sentence in plain English that says what the quote says about the topic. Name the \
source by a short name (for example "The VA/DoD guideline", "The CMS consensus document", "The ICRC manual", \
"The WHO standards"). Say whom the source says it applies to, in the source's own terms (for example "for \
prosthetic ambulators", "at the K2 level", "TT", "unilateral"). Put nothing in the sentence that the quote does \
not say. {FAITHFULNESS}
4. sentence_ar is the same sentence in Modern Standard Arabic. Use the Arabic terms of the specialist's page, the \
same term every time: {terms_line(ARABIC_TERMS)}. The quote stays in its own language; never translate it.
5. Report; never advise. Do not recommend, prescribe, choose or rank components, devices or treatments, do not \
diagnose, and do not say or suggest whether this patient is or is not ready for fitting. Never write in your \
own voice that something "should" be done for this patient; when a source recommends something, attribute it \
("The VA/DoD guideline suggests ...").
6. Where passages disagree, give each side as its own item.
7. Report only what bears on this case: its amputation level, side and, if recorded, functional level. If no \
passage says anything relevant to a topic, give no item for it. Never stretch a passage to fit a topic.
8. grade: if the passage prints the source's strength of recommendation right after the quoted \
recommendation, copy it ({", ".join(GRADE_PHRASES)}); otherwise "". Never infer a grade.
9. Prefer guideline recommendations and the passages most specific to this case. At most \
{MAX_ITEMS_PER_TOPIC} items per topic, and at most one per topic when the topics are missing information."""

TASKS = {
    GAPS: "The topics are pieces of information missing from this case's intake. For each one, find a passage "
          "that says why this information matters when a person with an amputation is assessed for, or fitted "
          "with, a prosthesis (for example, that it is assessed, or what it affects). sentence_en says what the "
          "source says about it. At most one item per topic.",
    COMPONENTS_PART: "The topics are the components of this case's prosthesis and, for a lower limb, its "
                     "functional level (K-level). For each component, report what the passages say about it "
                     "for this case. For the functional level, report how the source describes the recorded "
                     "K-level (or, if none is recorded, the K-levels), and what the source says K-levels are "
                     "or are not.",
    FITTING: "The topics are the design and fitting of this case's prosthesis: readiness for fitting, a "
             "preparatory or definitive prosthesis, the fitting process, and alignment. For each, report what "
             "the passages say for this case. For readiness, report the source's criteria; never say whether "
             "this patient meets them.",
}
MAX_ITEMS = {GAPS: 1, COMPONENTS_PART: MAX_ITEMS_PER_TOPIC, FITTING: MAX_ITEMS_PER_TOPIC}
CASE_HEADING = "CASE (fictional; amputation level, side and recorded functional level only; null means not recorded)"


def case_for_prompt(case: Case) -> str:
    """What the writer is told about the case: only the facts its rules use.

    Rule 7 of SYSTEM_PROMPT makes the amputation level, side and recorded
    functional level the only case facts that decide what bears on the case,
    and the missing fields arrive as the topics; for readiness the model
    reports the source's criteria, never whether the patient meets them. So
    nothing typed at intake is sent (since 2026-10-16, prompt rag-v2; before,
    the whole case went): free text is how an identifier could leave the
    machine (CLAUDE.md principle 4), and an opinion in it ("confirm K4
    components") could steer the model.
    """
    data = {
        "amputation_level": case.amputation_level.value,
        "limb": "lower" if case.is_lower_limb else "upper",
        "side": case.side.value,
        "functional_level_recorded": recorded_k_level(case),
    }
    return json.dumps(data, ensure_ascii=False, indent=1)


PROFILE = Profile(PARTS, SYSTEM_PROMPT, TASKS, MAX_ITEMS, case_for_prompt, CASE_HEADING, PROMPT_VERSION)


def components_from(case: Case, generation: Generation) -> ComponentSupport:
    """The functional level and the components, section by section."""
    part = generation.part(COMPONENTS_PART)
    functional = FunctionalLevel(lower_limb=case.is_lower_limb, k_level=recorded_k_level(case),
                                 activity=case.activity.description, goals=case.activity.functional_goals)
    sections = []
    if case.is_lower_limb:
        sections.append(ComponentSection(FUNCTIONAL_LEVEL, statements_for(part, FUNCTIONAL_LEVEL)))
    for info in COMPONENTS:
        statements = statements_for(part, info.key)
        if statements or case.amputation_level in info.levels:
            sections.append(ComponentSection(info.key, statements))
    return ComponentSupport(functional, sections)


def fitting_from(case: Case, generation: Generation) -> FittingSupport:
    """Design and fitting, section by section, with the intake values the readiness statements speak about."""
    part = generation.part(FITTING)
    sections = [ComponentSection(info.key, statements_for(part, info.key))
                for info in SECTIONS if case.amputation_level in info.levels]
    return FittingSupport(sections, [(path, recorded_value(case, path)) for path in READINESS_FIELDS])
