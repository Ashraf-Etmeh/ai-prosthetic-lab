"""Review decision log: every specialist decision, appended to a JSON-lines file.

This is the brief's last pathway step, "documented outcome". Each decision
becomes one line of REVIEW_LOG_PATH (data/review_log.jsonl): a complete JSON
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
- the language of the review page ("ui_language", "en" or "ar"). Labels
  and explanations are logged in English whichever language was shown;
  the Arabic page shows the same items, translated (shared/i18n.py),
- the settings that produced the gap list.

Lines are only ever added. Editing or removing a logged decision is out of
scope for v1 (FUTURE_WORK.md).
"""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from reasoning.models import CitedStatement, ComponentSupport, Gap
from shared.config import (
    EMBEDDING_MODEL_NAME,
    EMBEDDING_MODEL_REVISION,
    MIN_RELEVANCE_SCORE,
    RETRIEVAL_DOMAINS,
    RETRIEVAL_LANGUAGES,
    RETRIEVAL_TOP_K,
    REVIEW_LOG_PATH,
)
from shared.i18n import DEFAULT_LANGUAGE, TranslatableError
from shared.store import CaseRecord

DECISIONS = ("approve", "edit", "reject")
GAP_JUDGEMENTS = ("needed", "not_needed")
STATEMENT_JUDGEMENTS = ("relevant", "not_relevant")
# Raise when the shape of an entry changes. 2 (2026-10-08): adds "ui_language";
# version 1 entries were all made on the English page. 3 (2026-10-08): adds
# "components" (functional level and component statements).
LOG_VERSION = 3

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
) -> dict:
    """The log entry for one decision. Raises InvalidDecision if it is not valid.

    gap_judgements maps a gap's field path to "needed" or "not_needed";
    statement_judgements maps a component statement's id to "relevant" or
    "not_relevant". Gaps and statements left out are logged as not marked
    (None).
    """
    note = (note or "").strip() or None
    gap_judgements = gap_judgements or {}
    statement_judgements = statement_judgements or {}
    if decision not in DECISIONS:
        raise InvalidDecision("error.unknown_decision", decision=decision)
    if decision == "edit" and note is None:
        raise InvalidDecision("error.edit_needs_note")
    gap_fields = {gap.field for gap in record.gaps}
    for field, judgement in gap_judgements.items():
        if field not in gap_fields:
            raise InvalidDecision("error.not_a_gap", field=field)
        if judgement not in GAP_JUDGEMENTS:
            raise InvalidDecision("error.unknown_judgement", judgement=judgement, field=field)
    shown = {c.statement.id for c in record.components.statements} if record.components else set()
    for statement_id, judgement in statement_judgements.items():
        if statement_id not in shown:
            raise InvalidDecision("error.not_a_statement", statement=statement_id)
        if judgement not in STATEMENT_JUDGEMENTS:
            raise InvalidDecision("error.unknown_judgement", judgement=judgement, field=statement_id)

    return {
        "log_version": LOG_VERSION,
        "logged_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "case_id": record.case.case_id,
        "decision": decision,
        "note": note,
        "ui_language": ui_language,
        "gaps": [_gap_entry(gap, gap_judgements.get(gap.field)) for gap in record.gaps],
        "components": _components_entry(record.components, statement_judgements),
        "knowledge_warning": record.knowledge_warning,  # set if no sources were searched
        "settings": {
            "embedding_model": EMBEDDING_MODEL_NAME,
            "embedding_revision": EMBEDDING_MODEL_REVISION,
            "min_relevance_score": MIN_RELEVANCE_SCORE,
            "retrieval_languages": list(RETRIEVAL_LANGUAGES),
            "retrieval_domains": list(RETRIEVAL_DOMAINS),
            "retrieval_top_k": RETRIEVAL_TOP_K,
        },
        "case": record.case.to_dict(),
    }


def _gap_entry(gap: Gap, judgement: Optional[str]) -> dict:
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
        "reviewer_judgement": judgement,  # "needed", "not_needed", or None (not marked)
        "source": source,  # None: the gap cited no passage
    }


def _quoted(cited: CitedStatement) -> dict:
    statement = cited.statement
    return {
        "id": statement.id,
        "doc_id": statement.doc_id,
        "citation": cited.citation(statement.quote),
        "quote": statement.quote.text,
    }


def _components_entry(support: Optional[ComponentSupport], judgements: dict[str, str]) -> Optional[dict]:
    if support is None:
        return None
    functional = support.functional
    return {
        "functional_level": {
            "lower_limb": functional.lower_limb,
            "k_level": functional.k_level,
            "description": _quoted(functional.description) if functional.description else None,
            "cautions": [_quoted(cited) for cited in functional.cautions],
        },
        "notes": list(support.notes),  # why some statements were left out
        "sections": [
            {
                "component": section.component,
                "statements": [
                    {
                        **_quoted(cited),
                        "component": cited.statement.component,
                        "grade": cited.statement.grade,  # the source's own; None if it gives none
                        "context": [
                            {"citation": cited.citation(quote), "quote": quote.text}
                            for quote in cited.statement.context
                        ],
                        # "relevant", "not_relevant", or None (not marked)
                        "reviewer_judgement": judgements.get(cited.statement.id),
                    }
                    for cited in section.statements
                ],
            }
            for section in support.sections
        ],
    }


def record_decision(
    record: CaseRecord,
    decision: str,
    note: Optional[str] = None,
    gap_judgements: Optional[dict[str, str]] = None,
    path: Optional[Path] = None,
    ui_language: str = DEFAULT_LANGUAGE,
    statement_judgements: Optional[dict[str, str]] = None,
) -> dict:
    """Validate the decision, append it to the log as one line, and return the entry."""
    entry = build_entry(record, decision, note, gap_judgements, ui_language, statement_judgements)
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
