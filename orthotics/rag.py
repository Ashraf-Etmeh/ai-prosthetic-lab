"""The orthotic RAG: the instructions for the AI, what it is told about the case, and the page's sections.

Same pipeline and checks as prosthetics (reasoning/rag.py): the search finds
passages per topic (orthotics/topics.py), the writer answers each part as
JSON, and every item's quote is checked word for word against its passage
before it is shown. Only what differs lives here: the instructions (worded
for an orthotist and an ankle-foot orthosis), the case facts the writer may
see, and how the kept items become the review page's sections.

IMPORTANT: the instructions forbid advice. The AI reports what the sources
say; it never chooses or ranks a device, sets an angle, a material or a
wearing time, or says whether this patient should have an orthosis or FES.
The orthotist decides, and writes the choice and its reason in the decision.
"""

import json

from reasoning.fitting_support import recorded_value
from reasoning.models import ComponentSection, ComponentSupport, FittingSupport
from reasoning.rag import FAITHFULNESS, GRADE_PHRASES, Generation, Profile, _statements, terms_line
from reasoning.rag_topics import GAPS
from shared.case_schema import OrthoticCase
from shared.config import MAX_ITEMS_PER_TOPIC
from orthotics.topics import DESIGN_FITTING, DESIGN_SECTIONS, DEVICE_SECTIONS, DEVICES, PARTS

# Changes whenever these instructions change; logged with every decision. rag-ort-v2
# (2026-10-23): reasoning/rag.py FAITHFULNESS and the page's Arabic terms, as rag-v3.
PROMPT_VERSION = "rag-ort-v2"

# The orthotic review page's Arabic terms (shared/i18n.py; checked in tests/test_orthotics.py).
ARABIC_TERMS = (
    ("ankle-foot orthosis, AFO", "جهاز تقويم الكاحل والقدم"),
    ("orthosis", "الجهاز التقويمي"),
    ("functional electrical stimulation, FES", "التنبيه الكهربائي الوظيفي"),
    ("gait", "المشية"),
    ("affected side", "الجانب المصاب"),
    ("design", "التصميم"),
    ("fitting", "التركيب"),
    ("trim lines", "خطوط القص"),
    ("outcome measures", "مقاييس النتائج"),
)

SYSTEM_PROMPT = f"""\
You help an orthotist review one fictional case of a person who may use an ankle-foot orthosis after a stroke. \
You receive the case's condition, affected side and months since onset, a list of topics, and passages that a \
search found in the orthotist's source library (guidelines, manuals and reviews). For each topic, you report in \
short sentences what the passages say that bears on this case. The orthotist reads each sentence next to the quote \
that backs it, and decides.

Rules:
1. Use only the passages given. Add nothing from outside them.
2. Each item backs one sentence with one quote. Copy the quote exactly, character for character, from the \
passage named by passage_id: one continuous stretch of text of at least five words, usually one or two whole \
sentences. Do not shorten it, join separate pieces, leave words out, add "...", fix typing errors or translate \
it. Code compares every quote with its passage and deletes any item whose quote is not found there.
3. sentence_en is one short sentence in plain English that says what the quote says about the topic. Name the \
source by a short name (for example "The VA/DoD stroke guideline", "The WHO rehabilitation package", "The ICRC \
manual", "The NICE guidance", "The meta-analysis"). Say whom the source says it applies to, in the source's own \
terms (for example "in chronic stroke", "for people with foot drop"). Put nothing in the sentence that the quote \
does not say. {FAITHFULNESS}
4. sentence_ar is the same sentence in Modern Standard Arabic. Use the Arabic terms of the orthotist's page, the \
same term every time: {terms_line(ARABIC_TERMS)}. The quote stays in its own language; never translate it.
5. Report; never advise. Do not recommend, prescribe, choose or rank orthoses, FES, devices or treatments, do not \
set angles, materials, trim lines or wearing times, do not diagnose, and do not say or suggest whether this \
patient should have an orthosis or FES. Never write in your own voice that something "should" be done for this \
patient; when a source recommends something, attribute it ("The VA/DoD stroke guideline suggests ...").
6. Where passages disagree, give each side as its own item.
7. Report only what bears on this case: a person after a stroke, the affected side and, if recorded, the months \
since onset. A passage about another condition (for example cerebral palsy, scoliosis, a diabetic foot or an \
amputation) bears on this case only if the source itself says it applies to stroke; otherwise give no item for \
it. If no passage says anything relevant to a topic, give no item for it. Never stretch a passage to fit a topic.
8. grade: if the passage prints the source's strength of recommendation right after the quoted \
recommendation, copy it ({", ".join(GRADE_PHRASES)}); otherwise "". Never infer a grade.
9. Prefer guideline recommendations and the passages most specific to this case. At most \
{MAX_ITEMS_PER_TOPIC} items per topic, and at most one per topic when the topics are missing information."""

TASKS = {
    GAPS: "The topics are pieces of information missing from this case's intake. For each one, find a passage "
          "that says why this information matters when a person after a stroke is assessed for, or fitted with, "
          "an ankle-foot orthosis or FES (for example, that it is assessed, or what it affects). sentence_en says "
          "what the source says about it. At most one item per topic.",
    DEVICES: "The topics are the options an orthotist weighs for walking after a stroke: an ankle-foot orthosis or "
             "FES, the types of ankle-foot orthosis, their effects and the limits of those effects, and when not "
             "to provide one. For each, report what the passages say for this case. Report options side by side; "
             "never rank them or say which this patient should have.",
    DESIGN_FITTING: "The topics are the design and fitting of an ankle-foot orthosis: design (ankle angle, "
                    "stiffness, trim lines, materials), fitting and check-out, the timing of provision and "
                    "training with the orthosis, and outcome measures. For each, report what the passages say. "
                    "Never set an angle, a material, a trim line or a wearing time for this patient.",
}
MAX_ITEMS = {GAPS: 1, DEVICES: MAX_ITEMS_PER_TOPIC, DESIGN_FITTING: MAX_ITEMS_PER_TOPIC}
CASE_HEADING = "CASE (fictional; condition, affected side and months since onset only; null means not recorded)"

# The intake values shown next to the design and fitting statements, as entered, never judged.
RECORDED_FIELDS = (
    "exam.dorsiflexion_knee_extended_deg",
    "exam.dorsiflexion_knee_flexed_deg",
    "exam.knee_in_stance",
    "exam.protective_sensation",
    "exam.skin_condition",
    "footwear",
    "donning",
    "body_weight_kg",
)


def case_for_prompt(case: OrthoticCase) -> str:
    """What the writer is told about the case: only the facts its rules use.

    Rule 7 makes the condition, the affected side and the months since onset
    the only case facts that decide what bears on the case; the missing
    fields arrive as the topics. Nothing typed at intake is sent (CLAUDE.md
    principle 4): free text is how an identifier could leave the machine, and
    an opinion in it could steer the model.
    """
    data = {
        "condition": case.condition.value,
        "limb": "lower",
        "affected_side": case.side.value,
        "months_since_onset": case.months_since_onset,
    }
    return json.dumps(data, ensure_ascii=False, indent=1)


PROFILE = Profile(PARTS, SYSTEM_PROMPT, TASKS, MAX_ITEMS, case_for_prompt, CASE_HEADING, PROMPT_VERSION)


def components_from(case: OrthoticCase, generation: Generation) -> ComponentSupport:
    """The orthosis and FES options, section by section (no functional level: that is a prosthetic K-level)."""
    part = generation.part(DEVICES)
    return ComponentSupport(None, [ComponentSection(key, _statements(part, key)) for key in DEVICE_SECTIONS])


def fitting_from(case: OrthoticCase, generation: Generation) -> FittingSupport:
    """Design and fitting, section by section, with the intake values they speak about."""
    part = generation.part(DESIGN_FITTING)
    sections = [ComponentSection(key, _statements(part, key)) for key in DESIGN_SECTIONS]
    return FittingSupport(sections, [(path, recorded_value(case, path)) for path in RECORDED_FIELDS])
