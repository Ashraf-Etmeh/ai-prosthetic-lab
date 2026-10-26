"""Smart search in the specialist library (use case 05; SYSTEM_DESIGN.md §7.3; plan Part 6, 2026-10-25).

find(): the local search over the whole library (the same index as the cases'),
in English and Arabic, narrowed by the reader's filters: domain, kind of source,
language and year. Passages come back in order of match, never of quality.

summarise(): what the passages say about the question, as AI sentences each over a
quote checked word for word (the same pipeline and checks as a case's,
reasoning/rag.py run_part, with the search's own instructions below). A question is
typed text: it goes to the cloud writer only once the owner sets SEARCH_CLOUD_AI
(off: owner's decision, 2026-10-25); until then the writer is never called and the
page shows the passages found. The evidence layer the design filters by belongs to
the knowledge items, not to passages, so it is not a filter here.
"""

import json
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

from knowledge.catalog import load_catalog
from knowledge.embedding import embed_texts
from knowledge.models import ProtocolChunk
from knowledge.retrieval import VectorStore, get_store
from reasoning.models import CitedStatement
from reasoning.rag import FAITHFULNESS, GRADE_PHRASES, Part, Profile, run_part, statements_for
from reasoning.rag_topics import Topic
from reasoning.writer import OfflineWriter, Writer, is_cloud
from shared import config

LANGUAGES = ("both", "en", "ar")  # "both": every language the app searches (config.RETRIEVAL_LANGUAGES)
FROM_YEARS = (2015, 2020)  # the "from year" choices
PART, TOPIC = "search", "question"


@dataclass(frozen=True)
class Filters:
    domains: tuple[str, ...] = ()  # catalog domains; () = every domain
    kinds: tuple[str, ...] = ()  # catalog source types; () = every kind
    language: str = "both"
    from_year: Optional[int] = None

    def to_dict(self) -> dict:
        return {"domains": list(self.domains), "kinds": list(self.kinds), "language": self.language,
                "from_year": self.from_year}


def left_out(filters: Filters, catalog=None) -> set[str]:
    """The documents a search leaves out for these filters: another kind, or older than the year."""
    catalog = load_catalog() if catalog is None else catalog
    return {doc.id for doc in catalog
            if (filters.kinds and doc.source_type not in filters.kinds)
            or (filters.from_year and (doc.year or 0) < filters.from_year)}


def find(question: str, filters: Filters, store: Optional[VectorStore] = None,
         embed: Callable[[list[str]], np.ndarray] = embed_texts, top_k: int = config.SEARCH_TOP_K,
         catalog=None) -> list[ProtocolChunk]:
    """The passages that best match the question, best first (KnowledgeBaseMissing before the library is built)."""
    store = store if store is not None else get_store()
    languages = config.RETRIEVAL_LANGUAGES if filters.language == "both" else (filters.language,)
    return store.search(embed([question])[0], top_k, filters.domains or None, languages,
                        exclude=left_out(filters, catalog))


SYSTEM_PROMPT = f"""\
You help a clinician in prosthetics, orthotics or rehabilitation read a specialist library. You receive a \
question typed by the clinician and passages that a search found in the library (guidelines, manuals and \
reviews). You report in short sentences what the passages say that answers the question. The clinician reads \
each sentence next to the quote that backs it, and decides.

Rules:
1. Use only the passages given. Add nothing from outside them.
2. Each item backs one sentence with one quote. Copy the quote exactly, character for character, from the \
passage named by passage_id: one continuous stretch of text of at least five words, usually one or two whole \
sentences. Do not shorten it, join separate pieces, leave words out, add "...", fix typing errors or translate \
it. Code compares every quote with its passage and deletes any item whose quote is not found there.
3. sentence_en is one short sentence in plain English that says what the quote says about the question. Name \
the source by a short name. Say whom the source says it applies to, in the source's own terms. Put nothing in \
the sentence that the quote does not say. {FAITHFULNESS}
4. sentence_ar is the same sentence in Modern Standard Arabic. The quote stays in its own language; never \
translate it.
5. Report; never advise. Do not recommend, prescribe, choose or rank devices, components or treatments, and do \
not diagnose. Give options in the order the passages mention them. When a source recommends something, \
attribute it ("The guideline suggests ...").
6. Where passages disagree, give each side as its own item.
7. If no passage answers the question, give no item. Never stretch a passage to fit the question.
8. grade: if the passage prints the source's strength of recommendation right after the quoted \
recommendation, copy it ({", ".join(GRADE_PHRASES)}); otherwise "". Never infer a grade.
9. At most {config.SEARCH_MAX_ITEMS} items."""

TASKS = {PART: "The one topic is the clinician's question. Report what the passages say that answers it."}
AI_OFF_REASON = ("a search question is typed text, so it is not sent to the cloud model until the owner switches "
                 "it on (shared/config.py SEARCH_CLOUD_AI, owner's decision 2026-10-25)")
PROFILE = Profile((PART,), SYSTEM_PROMPT, TASKS, {PART: config.SEARCH_MAX_ITEMS},
                  lambda question: json.dumps({"question": question}, ensure_ascii=False),
                  "QUESTION (typed by the clinician; answer only from the passages)", config.SEARCH_PROMPT_VERSION,
                  cloud_ai=lambda: config.SEARCH_CLOUD_AI, ai_off_reason=AI_OFF_REASON)


@dataclass
class Answer:
    """What the sources say about one question: the kept sentences, and the AI part as run (status, reason)."""

    part: Part
    statements: list[CitedStatement] = field(default_factory=list)


def summarise(question: str, passages: list[ProtocolChunk], writer: Writer) -> Answer:
    """The AI sentences over checked quotes; with the owner's switch off, a cloud writer is never called."""
    if is_cloud(writer) and not PROFILE.cloud_ai():
        writer = OfflineWriter(AI_OFF_REASON)
    part = run_part(PART, question, [Topic(TOPIC, PART, "The question", question)], {TOPIC: passages}, writer,
                    PROFILE)
    return Answer(part, statements_for(part, TOPIC))
