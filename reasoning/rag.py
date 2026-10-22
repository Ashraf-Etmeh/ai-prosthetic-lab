"""RAG: the passages the search found, summarised by the AI, every quote checked.

The owner's decision (2026-10-11): the review page's gaps, functional level,
components and design and fitting come from retrieval plus a language model
(a cloud language model, reasoning/writer.py), not from hand-written rules.

For a case:
1. The search (knowledge/retrieval.py) has found passages for every topic
   (reasoning/rag_topics.py): each missing field, the functional level, each
   component and each fitting section.
2. generate() asks the writer three questions at once, one per part (gaps,
   components, fitting). Each holds the fixed instructions (SYSTEM_PROMPT,
   versioned by PROMPT_VERSION), the case's amputation level, side and
   recorded K-level (nothing typed at intake: case_for_prompt()), the part's
   topics and their passages, each with its id. The answer is JSON (ANSWER_SCHEMA): a
   list of items, each a topic, a passage id, a quote, one sentence in
   English and Arabic, and the grade if the passage prints one.
3. Every item is checked (reasoning/quote_check.py). One that names a passage
   not given, or whose quote is not in it word for word, or is too short, or
   has no Arabic sentence, is removed, and the reason is kept (Part.removed),
   so the misquote rate can be measured. A grade not printed after the quote
   is dropped. What is shown is the passage's own words.
4. gaps_from(), components_from() and fitting_from() turn the kept items into
   the page's shapes (reasoning/models.py), so the review page, the decision
   log and the trial report work as before.

If the writer can't answer (no key, offline, refusal: Part.status
"unavailable"), the page still works: the gaps fall back to the search and
topic-word check of reasoning/gap_analysis.py, and each section lists the
passages found, without summaries.

IMPORTANT: the instructions forbid advice; the model reports what the
sources say for the case. The page labels every sentence as AI and shows the
checked quote under it. The specialist decides.
"""

import hashlib
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field, replace
from typing import Optional

from knowledge.models import ProtocolChunk
from reasoning.component_guide import COMPONENTS
from reasoning.component_support import cite, recorded_k_level
from reasoning.fitting_guide import READINESS_FIELDS, SECTIONS
from reasoning.fitting_support import recorded_value
from reasoning.gap_analysis import analyze_gaps, explain_gap
from reasoning.models import (
    FUNCTIONAL_LEVEL,
    ORIGIN_RAG,
    CitedStatement,
    ComponentSection,
    ComponentSupport,
    FittingSupport,
    FunctionalLevel,
    Gap,
    GuidelineStatement,
    Quote,
)
from reasoning.quote_check import QuoteRefused, find_quote, grade_after, locate_pages
from reasoning.rag_topics import COMPONENTS_PART, FITTING, GAPS, PARTS, Topic, topics_for_case
from reasoning.writer import Writer, WriterUnavailable
from shared.case_schema import Case
from shared.config import LLM_EFFORT, MAX_ITEMS_PER_TOPIC, PROMPT_VERSION
from shared.field_guide import missing_fields

log = logging.getLogger(__name__)

OK, UNAVAILABLE, NO_PASSAGES = "ok", "unavailable", "no passages"
# The strengths of recommendation a passage may print (VA/DoD's wording). A
# grade outside this list can't be given; "" is "none printed".
GRADE_PHRASES = ("Strong for", "Weak for", "Neither for nor against", "Weak against", "Strong against")
_ARABIC_LETTERS = re.compile("[؀-ۿ]")

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
not say.
4. sentence_ar is the same sentence in Modern Standard Arabic. The quote stays in its own language; never \
translate it.
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


@dataclass(frozen=True)
class Item:
    """One kept item: the AI's sentence and the quote that backs it, as found in the passage."""

    id: str  # "rag-<topic>-<10 hex>": the same topic and quote get the same id in every case
    topic: str
    chunk_id: str
    doc_id: str
    quote: str  # the passage's own words
    page: Optional[int]
    end_page: Optional[int]
    sentence_en: str
    sentence_ar: str
    grade: Optional[str] = None  # as printed after the quote; None if none


@dataclass
class Part:
    """What one model call gave for one part (gaps, components or fitting)."""

    kind: str  # GAPS, COMPONENTS_PART or FITTING
    status: str  # OK, UNAVAILABLE, or NO_PASSAGES (nothing to summarise: no call made)
    reason: Optional[str] = None  # why UNAVAILABLE, for the page and the log
    model: Optional[str] = None  # the model that answered
    usage: dict = field(default_factory=dict)
    seconds: Optional[float] = None
    topics: list[str] = field(default_factory=list)  # the topics asked about
    items: list[Item] = field(default_factory=list)
    # Items (or grades) the check took out: topic, passage_id, quote, reason, dropped ("item" or "grade").
    removed: list[dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == OK

    @property
    def removed_items(self) -> int:
        return sum(1 for entry in self.removed if entry["dropped"] == "item")

    def removed_for(self, topic: str) -> int:
        """How many of the AI's items for one topic the checks took out."""
        return sum(1 for entry in self.removed if entry["dropped"] == "item" and entry["topic"] == topic)


@dataclass
class Generation:
    """The AI part of a case's analysis: what was asked, of whom, and what was kept."""

    prompt_version: str
    writer: str  # the writer's name: the model asked, or "offline"
    effort: str
    parts: dict[str, Part]

    def part(self, name: str) -> Part:
        return self.parts[name]

    @property
    def unavailable(self) -> list[Part]:
        return [part for part in self.parts.values() if part.status == UNAVAILABLE]

    @property
    def answered_by(self) -> list[str]:
        """The models that actually answered (as the provider reported them), each once."""
        return sorted({part.model for part in self.parts.values() if part.status == OK and part.model})

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Generation":
        parts = {}
        for name, part in data["parts"].items():
            items = [Item(**item) for item in part.get("items", [])]
            parts[name] = Part(**{**part, "items": items})
        return cls(data["prompt_version"], data["writer"], data["effort"], parts)


# ---- Asking the writer ------------------------------------------------------


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


def answer_schema(topic_keys: list[str], passage_ids: list[str]) -> dict:
    """The JSON the answer must match. Topics and passage ids can only be ones given."""
    return {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string", "enum": topic_keys},
                        "passage_id": {"type": "string", "enum": passage_ids},
                        "quote": {"type": "string"},
                        "sentence_en": {"type": "string"},
                        "sentence_ar": {"type": "string"},
                        "grade": {"type": "string", "enum": ["", *GRADE_PHRASES]},
                    },
                    "required": ["topic", "passage_id", "quote", "sentence_en", "sentence_ar", "grade"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["items"],
        "additionalProperties": False,
    }


def _passages_of(topics: list[Topic], passages: dict[str, list[ProtocolChunk]]) -> dict[str, ProtocolChunk]:
    """The part's passages by id, each once, in the order found."""
    by_id: dict[str, ProtocolChunk] = {}
    for topic in topics:
        for chunk in passages.get(topic.key, []):
            by_id.setdefault(chunk.chunk_id, chunk)
    return by_id


def user_message(part: str, case: Case, topics: list[Topic], passages: dict[str, list[ProtocolChunk]]) -> str:
    found_for: dict[str, list[str]] = {}
    for topic in topics:
        for chunk in passages.get(topic.key, []):
            found_for.setdefault(chunk.chunk_id, []).append(topic.key)
    lines = ["TASK", TASKS[part], "",
             "CASE (fictional; amputation level, side and recorded functional level only; null means not "
             "recorded)", case_for_prompt(case), "",
             "TOPICS", *(f"- {topic.key}: {topic.label}" for topic in topics), "", "PASSAGES"]
    for chunk in _passages_of(topics, passages).values():
        pages = f"{chunk.page}" if not chunk.end_page or chunk.end_page == chunk.page else f"{chunk.page}-{chunk.end_page}"
        year = f" ({chunk.year})" if chunk.year else ""
        lines += [f'<passage id="{chunk.chunk_id}" source="{chunk.title}{year}" pages="{pages}" '
                  f'language="{chunk.language}" found_for="{", ".join(found_for[chunk.chunk_id])}">',
                  chunk.text, "</passage>"]
    return "\n".join(lines)


def item_id(topic: str, doc_id: str, quote: str) -> str:
    digest = hashlib.sha1(f"{doc_id}|{quote}".encode("utf-8")).hexdigest()[:10]
    return f"rag-{topic}-{digest}"


def check_items(part: str, answer: dict, topics: list[Topic], passages: dict[str, ProtocolChunk]) -> tuple[list[Item], list[dict]]:
    """The items that pass the checks, and what was removed and why."""
    keys = {topic.key for topic in topics}
    kept: list[Item] = []
    removed: list[dict] = []
    per_topic: dict[str, int] = {}
    for raw in answer.get("items", []) if isinstance(answer, dict) else []:
        topic, passage_id = str(raw.get("topic", "")), str(raw.get("passage_id", ""))
        quote = str(raw.get("quote", ""))
        sentence_en, sentence_ar = str(raw.get("sentence_en", "")).strip(), str(raw.get("sentence_ar", "")).strip()

        def drop(reason: str, what: str = "item") -> None:
            removed.append({"topic": topic, "passage_id": passage_id, "quote": quote, "reason": reason,
                            "dropped": what})

        if topic not in keys:
            drop("not one of the topics asked about")
            continue
        chunk = passages.get(passage_id)
        if chunk is None:
            drop("names a passage that was not given")
            continue
        try:
            shown = find_quote(quote, chunk.text)
        except QuoteRefused as error:
            drop(str(error))
            continue
        if not sentence_en:
            drop("no English sentence")
            continue
        if not _ARABIC_LETTERS.search(sentence_ar):
            drop("no Arabic sentence")
            continue
        new_id = item_id(topic, chunk.doc_id, shown)
        if any(item.id == new_id for item in kept):
            drop("the same quote again for this topic")
            continue
        if per_topic.get(topic, 0) >= MAX_ITEMS[part]:
            drop(f"more than {MAX_ITEMS[part]} item(s) for this topic")
            continue
        grade = str(raw.get("grade") or "").strip() or None
        if grade and (grade not in GRADE_PHRASES or not grade_after(grade, shown, chunk.text)):
            drop(f"grade {grade!r} not printed after the quote", what="grade")
            grade = None
        page, end_page = locate_pages(shown, chunk.doc_id, chunk.page, chunk.end_page)
        per_topic[topic] = per_topic.get(topic, 0) + 1
        kept.append(Item(new_id, topic, chunk.chunk_id, chunk.doc_id, shown, page, end_page,
                         sentence_en, sentence_ar, grade))
    return kept, removed


def run_part(part: str, case: Case, topics: list[Topic], passages: dict[str, list[ProtocolChunk]],
             writer: Writer) -> Part:
    asked = [topic for topic in topics if passages.get(topic.key)]
    result = Part(part, NO_PASSAGES, topics=[topic.key for topic in asked])
    if not asked:
        return result  # nothing found to summarise: no call
    by_id = _passages_of(asked, passages)
    try:
        answer = writer.write(SYSTEM_PROMPT, user_message(part, case, asked, passages),
                              answer_schema([topic.key for topic in asked], list(by_id)))
    except WriterUnavailable as error:
        result.status, result.reason = UNAVAILABLE, str(error)
        return result
    except Exception as error:  # a fault here must not take the page down: shown and logged as unavailable
        log.exception("the %s part failed", part)
        result.status, result.reason = UNAVAILABLE, f"unexpected error: {type(error).__name__}: {error}"
        return result
    result.status, result.model, result.usage, result.seconds = OK, answer.model, answer.usage, answer.seconds
    result.items, result.removed = check_items(part, answer.data, asked, by_id)
    return result


def generate(case: Case, passages: dict[str, list[ProtocolChunk]], writer: Writer,
             topics: Optional[list[Topic]] = None) -> Generation:
    """The three parts, asked at the same time. `passages` maps topic keys to the passages found."""
    topics = topics if topics is not None else topics_for_case(case)
    with ThreadPoolExecutor(max_workers=len(PARTS)) as pool:
        futures = {part: pool.submit(run_part, part, case, [t for t in topics if t.part == part], passages, writer)
                   for part in PARTS}
        parts = {part: future.result() for part, future in futures.items()}
    effort = getattr(writer, "effort", LLM_EFFORT)
    return Generation(PROMPT_VERSION, writer.name, effort, parts)


# ---- The page's shapes ------------------------------------------------------


def _cited(item: Item) -> CitedStatement:
    statement = GuidelineStatement(id=item.id, component=item.topic, doc_id=item.doc_id, grade=item.grade,
                                   quote=Quote(item.page, item.quote, item.end_page))
    return replace(cite(statement), origin=ORIGIN_RAG, summary_en=item.sentence_en,
                   summary_ar=item.sentence_ar, chunk_id=item.chunk_id)


def _statements(part: Part, topic: str) -> list[CitedStatement]:
    return [_cited(item) for item in part.items if item.topic == topic]


def gaps_from(case: Case, retrieved: dict[str, list[ProtocolChunk]], generation: Generation) -> list[Gap]:
    """The gap list. Without the AI's answer, the search and topic-word check of gap_analysis.py."""
    part = generation.part(GAPS)
    if not part.ok:
        return analyze_gaps(case, retrieved)
    missing = missing_fields(case)
    # The passages asked about: the item may quote one found for another missing field.
    asked = {chunk.chunk_id: chunk for field_ in missing for chunk in retrieved.get(field_.info.path, [])}
    gaps = []
    for field_ in missing:
        info = field_.info
        item = next((i for i in part.items if i.topic == info.path), None)
        chunk = asked.get(item.chunk_id) if item else None
        gap = Gap(field=info.path, label=info.label, status=field_.status, why_needed="",
                  source_protocol_reference=chunk.chunk_id if chunk else None, evidence=chunk,
                  excerpt=item.quote if chunk else None,
                  summary_en=item.sentence_en if chunk else None, summary_ar=item.sentence_ar if chunk else None)
        gap.why_needed = explain_gap(gap, "en")
        gaps.append(gap)
    return gaps


def components_from(case: Case, generation: Generation) -> ComponentSupport:
    part = generation.part(COMPONENTS_PART)
    functional = FunctionalLevel(lower_limb=case.is_lower_limb, k_level=recorded_k_level(case),
                                 activity=case.activity.description, goals=case.activity.functional_goals)
    sections = []
    if case.is_lower_limb:
        sections.append(ComponentSection(FUNCTIONAL_LEVEL, _statements(part, FUNCTIONAL_LEVEL)))
    for info in COMPONENTS:
        statements = _statements(part, info.key)
        if statements or case.amputation_level in info.levels:
            sections.append(ComponentSection(info.key, statements))
    return ComponentSupport(functional, sections)


def fitting_from(case: Case, generation: Generation) -> FittingSupport:
    part = generation.part(FITTING)
    sections = [ComponentSection(info.key, _statements(part, info.key))
                for info in SECTIONS if case.amputation_level in info.levels]
    return FittingSupport(sections, [(path, recorded_value(case, path)) for path in READINESS_FIELDS])
