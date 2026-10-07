"""Data model for a retrieved protocol chunk.

This is intentionally separate from the ingestion/storage implementation
so the reasoning layer can depend on a stable shape regardless of how the
chunks are stored.
"""

from dataclasses import dataclass
from typing import Optional


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
