"""In-memory case store for the prototype.

There is no database in v1. A case is created by intake, analyzed once, and
held in memory so the review page can display it by case_id. This does not
survive a server restart — that's fine for a local prototype. Only the
review *decisions* (approve/edit/reject) are persisted to disk, via
review/logging.py, once step 5 deepens the review layer.
"""

from dataclasses import dataclass, field
from typing import Optional

from knowledge.models import ProtocolChunk
from reasoning.models import Gap
from shared.case_schema import Case


@dataclass
class CaseRecord:
    case: Case
    retrieved_chunks: list[ProtocolChunk] = field(default_factory=list)
    gaps: list[Gap] = field(default_factory=list)


class CaseStore:
    """Simple process-local dict store, keyed by case_id."""

    def __init__(self) -> None:
        self._records: dict[str, CaseRecord] = {}

    def save(self, record: CaseRecord) -> None:
        self._records[record.case.case_id] = record

    def get(self, case_id: str) -> Optional[CaseRecord]:
        return self._records.get(case_id)

    def all(self) -> list[CaseRecord]:
        return list(self._records.values())


# One shared instance for the whole app (single-process, local use only).
store = CaseStore()
