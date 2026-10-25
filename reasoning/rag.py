"""RAG: the passages the search found, summarised by the AI, every quote checked.

The owner's decision (2026-10-11): the review page's gaps, functional level,
components and design and fitting come from retrieval plus a language model
(a cloud language model, reasoning/writer.py), not from hand-written rules.

This is the pipeline every domain shares. What a domain asks lives in its own
rag.py (prosthetics/rag.py, orthotics/rag.py: its PROFILE, the instructions,
the case facts the writer may see, and its page sections), found through
shared/domains.py.

For a case:
1. The search (knowledge/retrieval.py) has found passages for every topic
   (reasoning/rag_topics.py and the domain's topics.py): for a prosthetic case,
   each missing field, the functional level, each component and each fitting section.
2. generate() asks the writer one question per part at once (for a prosthetic
   case: gaps, components, fitting). Each holds the domain's fixed instructions
   (its SYSTEM_PROMPT, versioned by its prompt version), the few case facts the
   domain sends (nothing typed at intake: its case_for_prompt()), the part's
   topics and their passages, each with its id. The answer is JSON (answer_schema()): a
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
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field, replace
from typing import Callable, Optional

from knowledge.models import ProtocolChunk
from reasoning.citations import cite
from reasoning.gap_analysis import analyze_gaps, explain_gap
from reasoning.models import (
    ORIGIN_RAG,
    CitedStatement,
    ComponentSupport,
    FittingSupport,
    Gap,
    GuidelineStatement,
    Quote,
)
from reasoning.quote_check import QuoteRefused, find_quote, grade_after, locate_pages
from reasoning.rag_topics import GAPS, Topic, topics_for_case
from reasoning.writer import OfflineWriter, Writer, WriterUnavailable, is_cloud
from shared import domains
from shared.case_schema import CaseCore
from shared.config import LLM_EFFORT, MAX_ITEMS_PER_TOPIC
from shared.field_guide import missing_fields

log = logging.getLogger(__name__)

OK, UNAVAILABLE, NO_PASSAGES = "ok", "unavailable", "no passages"
# Part.removed "dropped" for an item whose quote is already shown under an earlier topic (drop_repeats).
REPEAT = "repeat"
# The strengths of recommendation a passage may print (VA/DoD's wording). A
# grade outside this list can't be given; "" is "none printed".
GRADE_PHRASES = ("Strong for", "Weak for", "Neither for nor against", "Weak against", "Strong against")
_ARABIC_LETTERS = re.compile("[؀-ۿ]")

# Rule 3's second half (since rag-v3, 2026-10-23). The first live run kept every quote, but
# three sentences said more than theirs: a hedge dropped ("Evidence ... suggests" became a
# fact), a claim taken from the passage outside the quote, and "is carried out" made "must".
FAITHFULNESS = (
    "Keep the source's own certainty and strength: where it says that evidence suggests something, that "
    "something may happen, or that a study found it, say that, and never state it as a plain fact. Never turn a "
    "description (\"is carried out\", \"is used\") into an instruction (\"must\", \"should\"); write \"must\" or "
    "\"should\" only where the quote does. Take every part of the sentence from the quote itself, not from the "
    "rest of the passage or its heading."
)



def terms_line(terms: tuple[tuple[str, str], ...]) -> str:
    return "; ".join(f"{english} = {arabic}" for english, arabic in terms)




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
    # Items (or grades) the check took out: topic, passage_id, quote, reason, dropped ("item" or "grade",
    # or REPEAT: a quote shown under an earlier topic, not a failed check).
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

    def repeats_for(self, topic: str) -> int:
        """How many of the AI's items for one topic are shown under an earlier topic instead."""
        return sum(1 for entry in self.removed if entry["dropped"] == REPEAT and entry["topic"] == topic)


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




@dataclass(frozen=True)
class Profile:
    """What a domain's RAG asks: its parts, instructions and what the writer is told about a case.

    The checks (quote, page, grade, Arabic sentence) are the same for every
    domain; only these differ. Each domain's is its rag.py PROFILE
    (prosthetics/rag.py, orthotics/rag.py since 2026-10-22).
    """

    parts: tuple[str, ...]
    system_prompt: str
    tasks: dict
    max_items: dict
    case_for_prompt: Callable
    case_heading: str
    prompt_version: str
    # Whether the domain's cases may go to a cloud writer (asked at each run; the owner's switch, e.g.
    # shared/config.py ORTHOTIC_CLOUD_AI), and why its pages have no summaries while they may not.
    cloud_ai: Callable[[], bool] = lambda: True
    ai_off_reason: str = ""


def profile_for(case) -> "Profile":
    """The RAG profile of the case's domain (<domain>/rag.py PROFILE)."""
    return domains.part(case.domain, "rag").PROFILE


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


def user_message(part: str, case: CaseCore, topics: list[Topic], passages: dict[str, list[ProtocolChunk]],
                 profile: Optional[Profile] = None) -> str:
    profile = profile or profile_for(case)
    found_for: dict[str, list[str]] = {}
    for topic in topics:
        for chunk in passages.get(topic.key, []):
            found_for.setdefault(chunk.chunk_id, []).append(topic.key)
    lines = ["TASK", profile.tasks[part], "",
             profile.case_heading, profile.case_for_prompt(case), "",
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


def check_items(part: str, answer: dict, topics: list[Topic], passages: dict[str, ProtocolChunk],
                max_items: Optional[dict] = None) -> tuple[list[Item], list[dict]]:
    """The items that pass the checks, and what was removed and why.

    `max_items`: the most items kept per topic, by part (the profile's). Without it, every
    domain's rule: one per missing field, MAX_ITEMS_PER_TOPIC for the other parts.
    """
    limit = (max_items or {}).get(part, 1 if part == GAPS else MAX_ITEMS_PER_TOPIC)
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
        if per_topic.get(topic, 0) >= limit:
            drop(f"more than {limit} item(s) for this topic")
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


def run_part(part: str, case: CaseCore, topics: list[Topic], passages: dict[str, list[ProtocolChunk]],
             writer: Writer, profile: Optional[Profile] = None) -> Part:
    profile = profile or profile_for(case)
    asked = [topic for topic in topics if passages.get(topic.key)]
    result = Part(part, NO_PASSAGES, topics=[topic.key for topic in asked])
    if not asked:
        return result  # nothing found to summarise: no call
    by_id = _passages_of(asked, passages)
    try:
        answer = writer.write(profile.system_prompt, user_message(part, case, asked, passages, profile),
                              answer_schema([topic.key for topic in asked], list(by_id)))
    except WriterUnavailable as error:
        result.status, result.reason = UNAVAILABLE, str(error)
        return result
    except Exception as error:  # a fault here must not take the page down: shown and logged as unavailable
        log.exception("the %s part failed", part)
        result.status, result.reason = UNAVAILABLE, f"unexpected error: {type(error).__name__}: {error}"
        return result
    result.status, result.model, result.usage, result.seconds = OK, answer.model, answer.usage, answer.seconds
    result.items, result.removed = check_items(part, answer.data, asked, by_id, profile.max_items)
    return result


def generate(case: CaseCore, passages: dict[str, list[ProtocolChunk]], writer: Writer,
             topics: Optional[list[Topic]] = None) -> Generation:
    """The three parts, asked at the same time. `passages` maps topic keys to the passages found.

    A case whose domain's profile keeps it from the cloud (an orthotic case while
    ORTHOTIC_CLOUD_AI is off) never reaches a cloud writer, whoever passes the
    writer (the app, the trial loader, golden_cases --rag).
    """
    profile = profile_for(case)
    if is_cloud(writer) and not profile.cloud_ai():
        writer = OfflineWriter(profile.ai_off_reason)
    topics = topics if topics is not None else topics_for_case(case)
    with ThreadPoolExecutor(max_workers=len(profile.parts)) as pool:
        futures = {part: pool.submit(run_part, part, case, [t for t in topics if t.part == part], passages, writer,
                                     profile)
                   for part in profile.parts}
        parts = {part: future.result() for part, future in futures.items()}
    drop_repeats(parts, [part for part in profile.parts if part != GAPS])
    effort = getattr(writer, "effort", LLM_EFFORT)
    return Generation(profile.prompt_version, writer.name, effort, parts)


def _flat(text: str) -> str:
    return " ".join(text.split())


def drop_repeats(parts: dict[str, Part], kinds: list[str]) -> None:
    """Show a quote once: an item whose quote (same document) holds or is held by one already kept,
    in these parts and in order, is moved to Part.removed as a REPEAT, naming the topic it is shown under.

    The parts are asked separately, so the AI can't see that it gave a quote under another
    part's topic (the first live run: CMS's K3 note under the functional level and again under
    preparatory or definitive). The gaps are not part of this: a gap says why a field matters.
    """
    shown: list[tuple[str, str, str]] = []  # (document, quote, topic) kept so far
    for kind in kinds:
        part = parts[kind]
        kept = []
        for item in part.items:
            quote = _flat(item.quote)
            earlier = next((topic for doc_id, text, topic in shown
                            if doc_id == item.doc_id and (quote in text or text in quote)), None)
            if earlier is None:
                shown.append((item.doc_id, quote, item.topic))
                kept.append(item)
            else:
                part.removed.append({"topic": item.topic, "passage_id": item.chunk_id, "quote": item.quote,
                                     "reason": f"the same quote is shown under {earlier}", "dropped": REPEAT})
        part.items = kept


# ---- The page's shapes ------------------------------------------------------


def _cited(item: Item) -> CitedStatement:
    statement = GuidelineStatement(id=item.id, component=item.topic, doc_id=item.doc_id, grade=item.grade,
                                   quote=Quote(item.page, item.quote, item.end_page))
    return replace(cite(statement), origin=ORIGIN_RAG, summary_en=item.sentence_en,
                   summary_ar=item.sentence_ar, chunk_id=item.chunk_id)


def statements_for(part: Part, topic: str) -> list[CitedStatement]:
    return [_cited(item) for item in part.items if item.topic == topic]


def gaps_from(case: CaseCore, retrieved: dict[str, list[ProtocolChunk]], generation: Generation) -> list[Gap]:
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


def components_from(case: CaseCore, generation: Generation) -> ComponentSupport:
    """What the sources say about the case's components or devices (<domain>/rag.py components_from)."""
    return domains.part(case.domain, "rag").components_from(case, generation)


def fitting_from(case: CaseCore, generation: Generation) -> FittingSupport:
    """What the sources say about design and fitting (<domain>/rag.py fitting_from)."""
    return domains.part(case.domain, "rag").fitting_from(case, generation)
