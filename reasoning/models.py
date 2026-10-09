"""Data model for the reasoning layer's output.

- Gap: one piece of information that appears to be missing before a case is
  ready for specialist evaluation (reasoning/gap_analysis.py).
- ComponentSupport: what the guidelines in the library say about the
  prosthetic components for this case, and the functional level they depend
  on (reasoning/component_support.py). Every statement is quoted word for
  word with its source and grade; none is the system's own advice.

Neither is a prescription: see shared/config.py DISCLAIMER. The specialist
decides.
"""

from dataclasses import dataclass, field
from typing import Optional

from knowledge.models import ProtocolChunk


@dataclass
class Gap:
    field: str  # dotted Case field path, e.g. "residual_limb.wound_status"
    label: str  # the field's name for the reviewer, e.g. "Residual limb wound status"
    status: str  # "not recorded" or "recorded as unknown"
    why_needed: str  # plain-language reason, pointing at the cited passage
    # chunk_id of the cited passage. Always one of the chunks retrieved for
    # this field, so the specialist can check it. None: no passage found.
    source_protocol_reference: Optional[str] = None
    evidence: Optional[ProtocolChunk] = None  # the cited passage itself
    excerpt: Optional[str] = None  # its sentences that mention this field's topic


@dataclass(frozen=True)
class Quote:
    """Words copied exactly from a catalogued document, and the page they are on."""

    page: int  # as numbered in a PDF viewer, like ProtocolChunk.page
    text: str
    end_page: Optional[int] = None  # set when the words run onto the next page

    @property
    def pages(self) -> str:
        if self.end_page and self.end_page != self.page:
            return f"p. {self.page}-{self.end_page}"
        return f"p. {self.page}"


@dataclass(frozen=True)
class GuidelineStatement:
    """What one source says, quoted word for word. Never the system's own words."""

    id: str  # stable, e.g. "va_dod_ll_17_microprocessor_knee"; logged, and names the review choice
    component: str  # a reasoning/component_guide.py COMPONENTS key, or "functional_level"
    doc_id: str  # catalog id of the source document
    grade: Optional[str]  # the source's own strength, e.g. "Weak for"; None if it gives none
    quote: Quote
    context: tuple[Quote, ...] = ()  # same document: who it applies to, confidence, caveats


@dataclass(frozen=True)
class CitedStatement:
    """A statement with its document's title and year, ready to show and log."""

    statement: GuidelineStatement
    title: str
    year: Optional[int]
    language: str = "en"  # the document's, so the page can show the quote in its direction

    def citation(self, quote: Quote) -> str:
        """E.g. "Lower Limb Prosthetic Workgroup Consensus Document (2017), p. 10"."""
        year = f" ({self.year})" if self.year else ""
        return f"{self.title}{year}, {quote.pages}"


@dataclass
class ComponentSection:
    component: str  # COMPONENTS key, e.g. "knee"
    statements: list[CitedStatement]  # empty: no source in the library covers it for this case


@dataclass
class FunctionalLevel:
    """The functional level and goals that component choice depends on."""

    lower_limb: bool  # K-levels describe lower-limb prostheses only
    k_level: Optional[str] = None  # "K0".."K4"; None if not recorded, unknown or upper limb
    description: Optional[CitedStatement] = None  # the source's description of k_level
    all_levels: list[CitedStatement] = field(default_factory=list)  # K0-K4, for reference
    cautions: list[CitedStatement] = field(default_factory=list)  # what the source says K-levels are not
    activity: Optional[str] = None  # as recorded at intake
    goals: Optional[str] = None  # as recorded at intake


@dataclass
class ComponentSupport:
    functional: FunctionalLevel
    sections: list[ComponentSection]
    # Why some statements are not shown, as shared/i18n.py keys, e.g.
    # "components.k_not_recorded".
    notes: list[str] = field(default_factory=list)

    @property
    def statements(self) -> list[CitedStatement]:
        return [cited for section in self.sections for cited in section.statements]
