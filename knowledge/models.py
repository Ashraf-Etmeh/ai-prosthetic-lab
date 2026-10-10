"""Data models of the knowledge layer.

- ProtocolChunk: a retrieved passage with its citation and score.
- KnowledgeItem: one curated statement in the knowledge-item structure of
  the research brief, with its evidence fields (built by knowledge/items.py
  from reasoning/component_guide.py and reasoning/fitting_guide.py).

These are intentionally separate from the ingestion/storage implementation
so the reasoning layer can depend on a stable shape regardless of how the
chunks and items are stored.
"""

import re
from dataclasses import dataclass, fields
from typing import Optional

from knowledge.catalog import DOMAINS, SOURCE_TYPES


@dataclass
class ProtocolChunk:
    chunk_id: str  # "<catalog document id>-<4-digit number>", e.g. "lower_limb_amputation_va_dod_cpg_2024-0042"
    text: str
    source: str  # file the chunk came from, relative to data/sources/
    title: str = ""  # document title from the catalog
    year: Optional[int] = None
    page: Optional[int] = None  # page the chunk starts on, as numbered in a PDF viewer
    end_page: Optional[int] = None  # page it ends on (same as page unless it crosses a page break)
    language: str = "en"
    score: Optional[float] = None  # similarity to the query (-1 to 1), if the retriever set one

    @property
    def doc_id(self) -> str:
        """The catalog id of the document: the chunk id without its number."""
        return self.chunk_id.rsplit("-", 1)[0]

    @property
    def citation(self) -> str:
        """Short reference for the reviewer, e.g. "VA/DoD ... (2024), p. 42-43"."""
        year = f" ({self.year})" if self.year else ""
        if self.page is None:
            pages = ""
        elif self.end_page and self.end_page != self.page:
            pages = f", p. {self.page}-{self.end_page}"
        else:
            pages = f", p. {self.page}"
        return f"{self.title or self.source}{year}{pages}"


# Allowed values of a knowledge item's evidence fields, in the research
# brief's order. Who may set them: see CLAUDE.md (only the owner's rule
# table, data/knowledge/evidence_rules.csv, or the owner's own values).
UNASSIGNED = "unassigned"
EVIDENCE_LAYERS = ("established", "evidence-based practice", "emerging", "experimental", UNASSIGNED)
EVIDENCE_TAGS = ("direct evidence", "inferred", "proposed", "unknown", UNASSIGNED)
CONFIDENCE_LEVELS = ("high", "medium", "low", UNASSIGNED)
VALIDATION_STATUSES = ("unreviewed", "rule-assigned", "owner-reviewed", "specialist-reviewed")
# assigned_by: the id of a rule in the owner's table, "manual" (a value the
# owner gave), or "none" (nothing assigned yet).
RULE_ID = re.compile(r"R[0-9]+")
ASSIGNED_BY_WORDS = ("manual", "none")

# The clinical judgements, and with them who set them and how far they have
# been reviewed: the fields the team fills in, never the code.
CLINICAL_FIELDS = ("population", "limitations", "evidence_layer", "evidence_tag", "confidence")
TEAM_FIELDS = (*CLINICAL_FIELDS, "validation_status", "assigned_by")


@dataclass(frozen=True, kw_only=True)
class KnowledgeItem:
    """One curated statement as a knowledge item.

    The fields up to grade_as_printed copy what is already recorded: the
    statement, word for word, and its source. The TEAM_FIELDS hold clinical
    judgements and their review state; a new item has them unassigned and
    "unreviewed". Frozen, so a value can only change by making a new item
    (dataclasses.replace), which is checked again.
    """

    knowledge_id: str  # the statement id, e.g. "va_dod_ll_17_microprocessor_knee"
    statement: str  # the quote, word for word as printed
    # The list the statement introduces, item by item as printed, e.g. after
    # "Those who are ready for fitting". Empty for most statements.
    list_items: tuple[str, ...] = ()
    domain: str  # the brief's domain, one of knowledge/catalog.py DOMAINS
    topic: str  # component or fitting section key, e.g. "knee", "functional_level", "alignment"
    source_id: str  # catalog id of the source document
    citation: str  # title (year), page, e.g. "Lower Limb Prosthetic Workgroup Consensus Document (2017), p. 10"
    date: str  # the source's year as the catalog records it, e.g. "2017"
    source_type: str  # catalog source_type, e.g. "protocol", "professional_knowledge"
    grade_as_printed: str = ""  # the source's own grade exactly as stored, e.g. "Weak for"; "" if none
    population: str = ""
    limitations: str = ""
    evidence_layer: str = UNASSIGNED
    evidence_tag: str = UNASSIGNED
    confidence: str = UNASSIGNED
    validation_status: str = "unreviewed"
    assigned_by: str = "none"

    def __post_init__(self) -> None:
        name = self.knowledge_id if isinstance(self.knowledge_id, str) and self.knowledge_id else "(no id)"
        for field in fields(self):
            value = getattr(self, field.name)
            if field.name == "list_items":
                if not isinstance(value, tuple) or not all(isinstance(i, str) and i.strip() for i in value):
                    raise ValueError(f"{name}: list_items must be a tuple of texts, got {value!r}")
            elif not isinstance(value, str):
                raise ValueError(f"{name}: {field.name} must be text, got {value!r}")
        for required in ("knowledge_id", "statement", "domain", "topic", "source_id", "citation"):
            if not getattr(self, required).strip():
                raise ValueError(f"{name}: {required} is empty")
        if self.domain not in DOMAINS:
            raise ValueError(f"{name}: domain must be one of {sorted(DOMAINS)}, got {self.domain!r}")
        if self.source_type not in SOURCE_TYPES:
            raise ValueError(f"{name}: unknown source_type {self.source_type!r}")
        for field_name, allowed in (
            ("evidence_layer", EVIDENCE_LAYERS),
            ("evidence_tag", EVIDENCE_TAGS),
            ("confidence", CONFIDENCE_LEVELS),
            ("validation_status", VALIDATION_STATUSES),
        ):
            if getattr(self, field_name) not in allowed:
                raise ValueError(f"{name}: {field_name} must be one of {list(allowed)}, "
                                 f"got {getattr(self, field_name)!r}")
        if self.assigned_by not in ASSIGNED_BY_WORDS and not RULE_ID.fullmatch(self.assigned_by):
            raise ValueError(f"{name}: assigned_by must be a rule id such as 'R1', 'manual' or 'none', "
                             f"got {self.assigned_by!r}")
        # Nothing clinical without saying where it came from.
        clinical = [f for f in self.set_fields() if f in CLINICAL_FIELDS]
        if clinical and self.assigned_by == "none":
            raise ValueError(f"{name}: {', '.join(clinical)} set, but assigned_by is 'none'; "
                             "name the owner's rule (e.g. 'R1') or 'manual'")
        if self.validation_status == "rule-assigned" and not RULE_ID.fullmatch(self.assigned_by):
            raise ValueError(f"{name}: validation_status 'rule-assigned' needs the rule id in assigned_by, "
                             f"got {self.assigned_by!r}")

    def set_fields(self) -> list[str]:
        """The TEAM_FIELDS that are no longer as a new item has them."""
        defaults = {field.name: field.default for field in fields(self)}
        return [name for name in TEAM_FIELDS if getattr(self, name) != defaults[name]]
