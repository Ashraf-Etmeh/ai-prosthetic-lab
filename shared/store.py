"""In-memory case store for the prototype.

There is no database in v1. A case is created by intake, analyzed once, and
held in memory so the review page can display it by case_id. This does not
survive a server restart — that's fine for a local prototype. Only the
review *decisions* (approve/edit/reject) are saved to disk, by
review/decision_log.py, each with its own copy of the case, gap list,
component statements and design and fitting statements.
"""

from dataclasses import dataclass, field
from typing import Optional

from knowledge.models import ProtocolChunk
from reasoning.models import ComponentSupport, FittingSupport, Gap
from shared.case_schema import Case


@dataclass
class CaseRecord:
    case: Case
    # Passages retrieved for each missing field, keyed by dotted field path.
    retrieved_chunks: dict[str, list[ProtocolChunk]] = field(default_factory=dict)
    gaps: list[Gap] = field(default_factory=list)
    # Set when the source library couldn't be searched, e.g. not built yet.
    knowledge_warning: Optional[str] = None
    # What the guidelines say about this case's components (None: not run).
    components: Optional[ComponentSupport] = None
    # What the sources say about design and fitting for this case (None: not run).
    fitting: Optional[FittingSupport] = None

    def shown_statements(self) -> list:
        """Every component and fitting statement on the review page (CitedStatement)."""
        return [*(self.components.statements if self.components else []),
                *(self.fitting.statements if self.fitting else [])]


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
