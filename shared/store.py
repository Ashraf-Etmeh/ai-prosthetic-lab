"""Case store for the prototype: in memory, with one JSON file per case on disk.

There is no database. A case is created by intake, analysed once, kept in
memory and written to data/cases/<case_id>.json, so its review page still
works after the server restarts: a case that is not in memory is read from
its file the first time it is asked for.

A file holds the case as entered, the passages retrieved for it, the gaps
with their quotes, the "source library not searched" warning and (version 2,
since the RAG of 2026-10-11) the AI's answer as kept after the quote check:
everything the search and the AI produced, which a re-ingested library or a
second AI call might not produce again. The component and fitting sections
are worked out again from that answer when a file is read, without calling
the AI. A version 1 file (before the RAG) opens with its gaps; its component
and fitting sections are not available. What the reviewer saw at each
decision is in the review log (review/decision_log.py).

Cases hold no patient identifiers (shared/case_schema.py); the file is named
after the case's random case_id.
"""

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from knowledge.models import ProtocolChunk
from reasoning.models import ComponentSupport, FittingSupport, Gap
from reasoning.rag import Generation, components_from, fitting_from
from shared.case_schema import Case, case_from_dict
from shared.config import CASES_DIR

# Raise when the shape of a case file changes, and keep reading older files.
# 2 (2026-10-11): adds "generation", the AI's answer (RAG); the passages
# retrieved also hold the component, fitting and functional-level topics.
CASE_FILE_VERSION = 2

# What a case id may look like to be used as a file name (generated ids are
# 12 hexadecimal characters). Anything else is never looked up on disk.
_SAFE_CASE_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")


@dataclass
class CaseRecord:
    case: Case
    # Passages retrieved for the case, keyed by dotted field path (a missing
    # field) or topic key ("knee", "alignment", ...: reasoning/rag_topics.py).
    retrieved_chunks: dict[str, list[ProtocolChunk]] = field(default_factory=dict)
    gaps: list[Gap] = field(default_factory=list)
    # Set when the source library couldn't be searched, e.g. not built yet.
    knowledge_warning: Optional[str] = None
    # What the sources say about this case's components (None: not available).
    components: Optional[ComponentSupport] = None
    # What the sources say about design and fitting for this case (None: not available).
    fitting: Optional[FittingSupport] = None
    # The AI's answer, as kept after the quote check (None: made before the RAG).
    generation: Optional[Generation] = None

    def shown_statements(self) -> list:
        """Every component and fitting statement on the review page (CitedStatement)."""
        return [*(self.components.statements if self.components else []),
                *(self.fitting.statements if self.fitting else [])]

    def passage(self, chunk_id: Optional[str]) -> Optional[ProtocolChunk]:
        """A retrieved passage by its id (None if it is not among them)."""
        return next((chunk for chunks in self.retrieved_chunks.values() for chunk in chunks
                     if chunk.chunk_id == chunk_id), None)


def record_to_dict(record: CaseRecord) -> dict:
    return {
        "case_file_version": CASE_FILE_VERSION,
        "case": record.case.to_dict(),
        "knowledge_warning": record.knowledge_warning,
        "retrieved_chunks": {path: [asdict(chunk) for chunk in chunks]
                             for path, chunks in record.retrieved_chunks.items()},
        "gaps": [asdict(gap) for gap in record.gaps],  # evidence included as a plain dict
        "generation": record.generation.to_dict() if record.generation else None,
    }


def record_from_dict(data: dict) -> CaseRecord:
    case = case_from_dict(data["case"])  # a case without "domain" is a prosthetics case
    gaps = [
        Gap(**{**gap, "evidence": ProtocolChunk(**gap["evidence"]) if gap["evidence"] else None})
        for gap in data["gaps"]
    ]
    generation = Generation.from_dict(data["generation"]) if data.get("generation") else None
    return CaseRecord(
        case=case,
        retrieved_chunks={path: [ProtocolChunk(**chunk) for chunk in chunks]
                          for path, chunks in data["retrieved_chunks"].items()},
        gaps=gaps,
        knowledge_warning=data["knowledge_warning"],
        # Version 1 files hold no AI answer: their sections are not available.
        components=components_from(case, generation) if generation else None,
        fitting=fitting_from(case, generation) if generation else None,
        generation=generation,
    )


class CaseStore:
    """Cases by case_id: in memory, and in `folder` if one is given."""

    def __init__(self, folder: Optional[Path] = CASES_DIR) -> None:
        self.folder = folder  # None: memory only
        self._records: dict[str, CaseRecord] = {}

    def _path(self, case_id: str) -> Optional[Path]:
        if self.folder is None or not _SAFE_CASE_ID.fullmatch(case_id):
            return None
        return self.folder / f"{case_id}.json"

    def save(self, record: CaseRecord) -> None:
        case_id = record.case.case_id
        self._records[case_id] = record
        if self.folder is None:
            return
        path = self._path(case_id)
        if path is None:
            raise ValueError(f"case id {case_id!r} can't be used as a file name")
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write a temporary file, then rename it: a crash mid-write leaves the
        # old file (or none), never half a file.
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(record_to_dict(record), ensure_ascii=False, indent=1),
                             encoding="utf-8")
        os.replace(temporary, path)

    def get(self, case_id: str) -> Optional[CaseRecord]:
        record = self._records.get(case_id)
        if record is None:
            path = self._path(case_id)
            if path is not None and path.is_file():
                record = record_from_dict(json.loads(path.read_text(encoding="utf-8")))
                self._records[case_id] = record
        return record

    def all(self) -> list[CaseRecord]:
        """The cases in memory: saved or opened since the server started."""
        return list(self._records.values())


# One shared instance for the whole app (single-process, local use only).
store = CaseStore()
