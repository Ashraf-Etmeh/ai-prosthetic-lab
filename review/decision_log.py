"""Review decision log: every specialist decision, appended to a JSON-lines file.

This is the brief's last pathway step, "documented outcome". Each decision
becomes one line of REVIEW_LOG_PATH (data/records/review_log.jsonl): a complete JSON
object that can be read on its own, holding
- the decision (approve / edit / reject), the reviewer's note and the time,
- the reviewer's judgement on each gap: needed, not needed, or not marked,
- a copy of the case and of every gap as shown, including each cited
  passage's quote, citation and full text. Chunk ids change when the library
  is re-ingested with other settings, so the id alone would not show later
  what the specialist saw,
- the functional level shown (K-level and the source's description of it)
  and every component statement shown, with its quote, context, citation
  and grade, and the reviewer's judgement on it: relevant, not relevant,
  or not marked,
- the same for every design and fitting statement shown, plus the intake
  values shown next to the readiness statements,
- the language of the review page ("ui_language", "en" or "ar"). Labels
  and explanations are logged in English whichever language was shown;
  the Arabic page shows the same items, translated (shared/i18n.py),
- the settings that produced the gap list,
- since version 5 (the RAG, 2026-10-11): each statement's origin ("rag" or
  "guide"), the AI's sentences in English and Arabic, the passage it was
  found in (id and full text), and "generation": the prompt version, the
  model, and per part (gaps, components, fitting) whether the AI answered,
  why not, its token counts and time, and what the quote check removed,
- since version 7 (2026-10-23): "plan", an orthotic case's work after the
  analysis as the orthotist saved it (requirements with their findings and
  priorities, design options with their parts, marks and notes, the chosen
  option and its reason, the design steps and every parameter version:
  orthotics/plan.py); and the decision "design_choice", logged when the
  orthotist records the option chosen on the options page, with the reason
  as its note,
- since version 10 (2026-10-24, plan Part 3): the same for a prosthetic
  case: "plan" holds the prosthetist's work after the intake
  (prosthetics/plan.py: the rest of the assessment, requirements, component
  options, the configuration and its reason, fitting and follow-up), and
  "design_choice" is logged when the prosthetist records the configuration
  on modules 2-3,
- since version 11 (2026-10-25, plan Part 4, the design's "sign and record"):
  a statement may also be marked "summary_wrong" (the AI's sentence is wrong,
  whatever the source says); each gap keeps the reviewer's reason as typed
  ("reviewer_reason"); and "versions" names what made the page: the prompt
  version, the models that answered, and the source library's build
  (knowledge/library.py).

Lines are only ever added. Editing or removing a logged decision is out of
scope for v1 (FUTURE_WORK.md).
"""

import json
import threading
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from knowledge.library import library_version
from knowledge.retrieval import domains_for
from reasoning.models import CitedStatement, ComponentSection, ComponentSupport, FittingSupport, Gap, Quote
from reasoning.rag import Generation
from shared.config import (
    EMBEDDING_MODEL_NAME,
    EMBEDDING_MODEL_REVISION,
    MIN_QUOTE_WORDS,
    MIN_RELEVANCE_SCORE,
    RAG_TOP_K,
    RAG_TOPIC_EXCLUDED_DOCUMENTS,
    RETRIEVAL_LANGUAGES,
    RETRIEVAL_TOP_K,
    REVIEW_LOG_PATH,
)
from shared.i18n import DEFAULT_LANGUAGE, TranslatableError
from shared.store import CaseRecord

DECISIONS = ("approve", "edit", "reject")
# The specialist's choice on a module page (version 7, orthotics: the option chosen; version 10,
# prosthetics: the configuration). Logged only through record_design_choice(), never from the review
# page's form.
DESIGN_CHOICE = "design_choice"
GAP_JUDGEMENTS = ("needed", "not_needed")
# "summary_wrong" (version 11): the AI's sentence is wrong, whatever the source says (SYSTEM_DESIGN.md §7.2).
STATEMENT_JUDGEMENTS = ("relevant", "not_relevant", "summary_wrong")
MAX_REASON = 500  # characters in a gap's reason
# Raise when the shape of an entry changes. 2 (2026-10-08): adds "ui_language";
# version 1 entries were all made on the English page. 3 (2026-10-08): adds
# "components" (functional level and component statements). 4 (2026-10-09):
# adds "fitting" (design and fitting statements), "source_type" per
# statement, and "items" for a quote that introduces a list. 5 (2026-10-11,
# the RAG): adds "generation", per statement "origin", "summary_en",
# "summary_ar", "chunk_id" and "passage", per gap "summary_en" and
# "summary_ar", and the RAG settings. 6 (2026-10-22, orthotics): adds "domain"
# ("prosthetics" or "orthotics"); for an orthotic case "components" holds the
# orthosis and FES options with "functional_level" null, "fitting" its design
# and fitting, and "settings" the orthotic search domains. An entry without
# "domain" (versions 1-5) is a prosthetics case. 7 (2026-10-23): adds "plan"
# (null for a prosthetic case or an orthotic case with nothing saved yet) and
# the decision "design_choice"; an entry without "plan" (versions 1-6) has none.
# 8 (2026-10-23, prompt rag-v3): an entry of generation.parts.*.removed may
# have "dropped": "repeat", a quote already shown under an earlier topic (not
# a failed check: reasoning/rag.py drop_repeats); before, only "item" or "grade".
# 9 (2026-10-23, the design canvas's screens): "plan" gains the keys of case
# file version 4 (shared/store.py), an orthotic "case" gains goals by ICF level,
# "measured_how" and exam.ulcer_infection_or_poor_blood_supply, and a design
# choice's plan.chosen may be "F", the referral to discuss FES. Older lines
# lack these keys. 10 (2026-10-24, the prosthetic module pages): a prosthetic
# case's "plan" is its prosthetics/plan.py ProstheticPlan (null before: none
# existed), and a prosthetic "design_choice" logs the configuration, its
# plan.chosen a dict of component -> option id ("configuration"). Older lines
# have no prosthetic plan. 11 (2026-10-25, the design's review page): a statement's
# reviewer_judgement may be "summary_wrong"; each gap gains "reviewer_reason"
# (the reviewer's words, or null); the entry gains "versions" (prompt, models,
# library build). Older lines lack these keys and have no "summary_wrong".
LOG_VERSION = 11

# The development server answers requests in threads; one write at a time
# keeps two decisions from mixing into one line.
_write_lock = threading.Lock()


class InvalidDecision(TranslatableError):
    """A submitted decision the log refuses, with a message for the reviewer."""


def build_entry(
    record: CaseRecord,
    decision: str,
    note: Optional[str] = None,
    gap_judgements: Optional[dict[str, str]] = None,
    ui_language: str = DEFAULT_LANGUAGE,
    statement_judgements: Optional[dict[str, str]] = None,
    gap_reasons: Optional[dict[str, str]] = None,
) -> dict:
    """The log entry for one decision. Raises InvalidDecision if it is not valid.

    gap_judgements maps a gap's field path to "needed" or "not_needed";
    gap_reasons maps a gap's field path to the reviewer's reason, as typed;
    statement_judgements maps the id of a component or fitting statement
    to "relevant", "not_relevant" or "summary_wrong". Gaps and statements
    left out are logged as not marked (None).
    """
    note = (note or "").strip() or None
    gap_judgements = gap_judgements or {}
    gap_reasons = {field: reason.strip() for field, reason in (gap_reasons or {}).items() if (reason or "").strip()}
    statement_judgements = statement_judgements or {}
    if not decision:
        raise InvalidDecision("error.choose_decision")
    if decision not in DECISIONS and not (decision == DESIGN_CHOICE and record.plan and record.plan.chosen):
        raise InvalidDecision("error.unknown_decision", decision=decision)
    if decision == "edit" and note is None:
        raise InvalidDecision("error.edit_needs_note")
    gap_fields = {gap.field for gap in record.gaps}
    for field, judgement in gap_judgements.items():
        if field not in gap_fields:
            raise InvalidDecision("error.not_a_gap", field=field)
        if judgement not in GAP_JUDGEMENTS:
            raise InvalidDecision("error.unknown_judgement", judgement=judgement, field=field)
    for field, reason in gap_reasons.items():
        if field not in gap_fields:
            raise InvalidDecision("error.not_a_gap", field=field)
        if len(reason) > MAX_REASON:
            raise InvalidDecision("error.reason_too_long", n=MAX_REASON)
    shown = {cited.statement.id for cited in record.shown_statements()}
    for statement_id, judgement in statement_judgements.items():
        if statement_id not in shown:
            raise InvalidDecision("error.not_a_statement", statement=statement_id)
        if judgement not in STATEMENT_JUDGEMENTS:
            raise InvalidDecision("error.unknown_judgement", judgement=judgement, field=statement_id)

    return {
        "log_version": LOG_VERSION,
        "logged_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "case_id": record.case.case_id,
        "domain": record.case.domain,
        "decision": decision,
        "note": note,
        "ui_language": ui_language,
        "gaps": [_gap_entry(gap, gap_judgements.get(gap.field), gap_reasons.get(gap.field)) for gap in record.gaps],
        "components": _components_entry(record.components, statement_judgements, record),
        "fitting": _fitting_entry(record.fitting, statement_judgements, record),
        "generation": _generation_entry(record.generation),
        "knowledge_warning": record.knowledge_warning,  # set if no sources were searched
        "settings": {
            "embedding_model": EMBEDDING_MODEL_NAME,
            "embedding_revision": EMBEDDING_MODEL_REVISION,
            "min_relevance_score": MIN_RELEVANCE_SCORE,
            "retrieval_languages": list(RETRIEVAL_LANGUAGES),
            "retrieval_domains": list(domains_for(record.case)),
            "retrieval_top_k": RETRIEVAL_TOP_K,
            "rag_top_k": RAG_TOP_K,
            "rag_topic_excluded_documents": list(RAG_TOPIC_EXCLUDED_DOCUMENTS),
            "min_quote_words": MIN_QUOTE_WORDS,
        },
        "case": record.case.to_dict(),
        "plan": record.plan.to_dict() if record.plan else None,
        "versions": signed_versions(record),
    }


def signed_versions(record: CaseRecord) -> dict:
    """What made the page a decision is signed on: the prompt version, the models that answered, the library."""
    generation = record.generation
    return {
        "prompt": generation.prompt_version if generation else None,
        "models": generation.answered_by if generation else [],
        "library": library_version(),
    }


def _generation_entry(generation: Optional[Generation]) -> Optional[dict]:
    """What the AI was asked and what came of it; the kept items are in the sections."""
    if generation is None:
        return None
    return {
        "prompt_version": generation.prompt_version,
        "writer": generation.writer,  # the model asked, or "offline"
        "effort": generation.effort,
        "parts": {
            name: {
                "status": part.status,  # "ok", "unavailable" or "no passages"
                "reason": part.reason,  # why unavailable
                "model": part.model,  # the model that answered
                "usage": part.usage,
                "seconds": part.seconds,
                "topics": part.topics,
                "items_kept": len(part.items),
                "removed": part.removed,  # what the quote check took out, and why
            }
            for name, part in generation.parts.items()
        },
    }


def _gap_entry(gap: Gap, judgement: Optional[str], reason: Optional[str] = None) -> dict:
    evidence = gap.evidence
    source = None
    if evidence is not None:
        source = {
            "chunk_id": evidence.chunk_id,
            "citation": evidence.citation,
            "title": evidence.title,
            "year": evidence.year,
            "page": evidence.page,
            "end_page": evidence.end_page,
            "file": evidence.source,
            "language": evidence.language,
            "score": evidence.score,
            "quote": gap.excerpt,
            "passage": evidence.text,
        }
    return {
        "field": gap.field,
        "label": gap.label,
        "status": gap.status,
        "why_needed": gap.why_needed,
        "summary_en": gap.summary_en,  # the AI's sentence; None without the AI
        "summary_ar": gap.summary_ar,
        "reviewer_judgement": judgement,  # "needed", "not_needed", or None (not marked)
        "reviewer_reason": reason,  # the reviewer's words (version 11); None: none given
        "source": source,  # None: the gap cited no passage
    }


def _quote(cited: CitedStatement, quote: Quote) -> dict:
    entry = {"citation": cited.citation(quote), "quote": quote.text}
    if quote.items:  # the list the quote introduces
        entry["items"] = list(quote.items)
    return entry


def _quoted(cited: CitedStatement) -> dict:
    statement = cited.statement
    return {"id": statement.id, "doc_id": statement.doc_id, **_quote(cited, statement.quote)}


def _sections_entry(sections: list[ComponentSection], judgements: dict[str, str],
                    record: Optional[CaseRecord] = None) -> list[dict]:
    def passage(cited: CitedStatement) -> Optional[str]:
        chunk = record.passage(cited.chunk_id) if record is not None and cited.chunk_id else None
        return chunk.text if chunk else None

    return [
        {
            "component": section.component,
            "statements": [
                {
                    **_quoted(cited),
                    "component": cited.statement.component,
                    "grade": cited.statement.grade,  # the source's own; None if it gives none
                    "source_type": cited.source_type,  # e.g. "protocol", "professional_knowledge"
                    "context": [_quote(cited, quote) for quote in cited.statement.context],
                    "origin": cited.origin,  # "rag" (search + AI, quote checked) or "guide" (hand-written)
                    "summary_en": cited.summary_en,  # the AI's sentence; None for a hand-written statement
                    "summary_ar": cited.summary_ar,
                    "chunk_id": cited.chunk_id,  # the passage the quote was found in
                    "passage": passage(cited),  # its full text, as the AI saw it
                    # "relevant", "not_relevant", "summary_wrong" (version 11), or None (not marked)
                    "reviewer_judgement": judgements.get(cited.statement.id),
                }
                for cited in section.statements
            ],
        }
        for section in sections
    ]


def _components_entry(support: Optional[ComponentSupport], judgements: dict[str, str],
                      record: Optional[CaseRecord] = None) -> Optional[dict]:
    if support is None:
        return None
    functional = support.functional
    return {
        # None for an orthotic case (no K-level).
        "functional_level": {
            "lower_limb": functional.lower_limb,
            "k_level": functional.k_level,
            "description": _quoted(functional.description) if functional.description else None,
            "cautions": [_quoted(cited) for cited in functional.cautions],
        } if functional is not None else None,
        "notes": list(support.notes),  # why some statements were left out
        "sections": _sections_entry(support.sections, judgements, record),
    }


def _fitting_entry(support: Optional[FittingSupport], judgements: dict[str, str],
                   record: Optional[CaseRecord] = None) -> Optional[dict]:
    if support is None:
        return None
    return {
        # The intake values shown next to the readiness statements; None: not recorded.
        "recorded": {path: value.value if isinstance(value, Enum) else value
                     for path, value in support.recorded},
        "sections": _sections_entry(support.sections, judgements, record),
    }


def record_decision(
    record: CaseRecord,
    decision: str,
    note: Optional[str] = None,
    gap_judgements: Optional[dict[str, str]] = None,
    path: Optional[Path] = None,
    ui_language: str = DEFAULT_LANGUAGE,
    statement_judgements: Optional[dict[str, str]] = None,
    gap_reasons: Optional[dict[str, str]] = None,
) -> dict:
    """Validate the decision, append it to the log as one line, and return the entry."""
    if decision == DESIGN_CHOICE:  # only through record_design_choice()
        raise InvalidDecision("error.unknown_decision", decision=decision)
    return _append(build_entry(record, decision, note, gap_judgements, ui_language, statement_judgements,
                               gap_reasons), path)


def record_design_choice(record: CaseRecord, path: Optional[Path] = None,
                         ui_language: str = DEFAULT_LANGUAGE) -> dict:
    """Log the specialist's choice (record.plan.chosen: an orthotic option, or a prosthetic configuration), its
    reason as the note, and the whole plan."""
    return _append(build_entry(record, DESIGN_CHOICE, record.plan.choice_reason if record.plan else None,
                               ui_language=ui_language), path)


def _append(entry: dict, path: Optional[Path]) -> dict:
    path = path or REVIEW_LOG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, ensure_ascii=False)  # Arabic stays readable in the file
    with _write_lock, path.open("a", encoding="utf-8") as log:
        log.write(line + "\n")
    return entry


def read_decisions(case_id: Optional[str] = None, path: Optional[Path] = None) -> list[dict]:
    """Logged entries, oldest first; only those for case_id if given."""
    path = path or REVIEW_LOG_PATH
    if not path.is_file():
        return []
    entries = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [entry for entry in entries if case_id is None or entry["case_id"] == case_id]
