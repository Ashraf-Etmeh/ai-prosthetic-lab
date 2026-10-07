"""Text extraction: source documents -> cleaned text, page by page.

The first half of ingestion (step 3). For every document in
data/sources/catalog.json, this pulls the text out of the PDF (or .txt),
cleans it, and writes it to data/extracted/<id>.txt. Open those files to see
exactly what the system reads. Chunking and embedding (knowledge/ingest.py)
start from these files.

Run:  python -m knowledge.extract

Running it again overwrites data/extracted/, so hand edits there are lost.
"""

import logging
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pypdf import PdfReader

from knowledge.catalog import SourceDocument, find_unlisted_files, load_catalog
from shared.config import CATALOG_PATH, EXTRACTED_DIR, SOURCES_DIR, SOURCES_NOT_INGESTED

# pypdf logs hundreds of harmless "fontTools is required" warnings.
logging.getLogger("pypdf").setLevel(logging.ERROR)

MIN_PAGE_CHARS = 50  # a page with less text than this is probably a scanned image
# A line on at least this share of pages (and at least 3) is a page header or
# footer, e.g. "DGOU Leitlinie 187-061 ..." or the page number.
REPEATED_LINE_SHARE = 0.4

_SECTION_NUMBER = r"(?:\d+(?:\.\d+)*\.?[ \t]+)?"  # optional, e.g. the "11. " in "11. Literatur"
_REFERENCES_HEADING = re.compile(
    rf"^[ \t]*{_SECTION_NUMBER}"
    r"(references|bibliography|literature cited|literatur|literaturverzeichnis|المراجع)[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)
# An appendix after the reference list is the document's own text, so it is
# kept. Arabic headings come out of PDFs scrambled (": موجز1 الملحق" for
# "Annex 1: Summary"), so any short line containing الملحق counts.
_APPENDIX_HEADING = re.compile(
    rf"^[ \t]*{_SECTION_NUMBER}(appendix|appendices|annex|annexes|anhang)\b[^\n]{{0,60}}$"
    r"|^[^\n]{0,20}الملحق[^\n]{0,20}$",
    re.IGNORECASE | re.MULTILINE,
)
# Database search syntax, as in a review's "search strategy" appendix:
# ('amputation'/exp OR amputation:ti,ab OR ...), "Braces"[Mesh], orthosis[tw].
# Uppercase OR/AND only ((?-i:...) switches off IGNORECASE there), so the
# "or" and "and" of ordinary prose don't count.
_SEARCH_SYNTAX = re.compile(
    r"(?-i:\bOR\b|\bAND\b)|/exp\b|/de\b|:ti,ab|\[(?:mesh|tiab|tw|all fields|ptyp)[^\]]*\]",
    re.IGNORECASE,
)
SEARCH_SYNTAX_PER_LINE = 3  # a line with this many operators is search syntax
_HYPHEN_BREAK = re.compile(r"(\w+)-\n(\w+)")
_ARABIC_LETTERS = re.compile("[؀-ۿ]")
_ARABIC_DISPLAY_FORMS = re.compile("[ﭐ-﷿ﹰ-﻿]")
_PAGE_MARKER = re.compile(r"^--- page (\d+) ---$", re.MULTILINE)

Page = tuple[int, str]  # (page number as shown in a PDF viewer, starting at 1; text)


@dataclass
class ExtractedDocument:
    document: SourceDocument
    pages: list[Page]
    total_pages: int
    references_from_page: Optional[int] = None  # None: no references heading found
    appendix_from_page: Optional[int] = None  # an appendix after the references, kept
    repeated_lines_removed: int = 0  # distinct page header/footer lines removed
    search_lines_removed: int = 0  # lines of literature-search syntax removed
    warnings: list[str] = field(default_factory=list)

    def references_summary(self) -> str:
        """What happened to the reference list, in words."""
        if self.references_from_page is None:
            return "no references heading found"
        if self.appendix_from_page is None:
            return f"references from page {self.references_from_page} on removed"
        return (
            f"references from page {self.references_from_page} up to the appendix "
            f"on page {self.appendix_from_page} removed"
        )


# ---- Reading ------------------------------------------------------------


def read_pages(path: Path) -> list[str]:
    """Raw text of each page. A .txt file counts as one page."""
    if path.suffix.lower() == ".txt":
        return [path.read_text(encoding="utf-8")]
    return [page.extract_text() or "" for page in PdfReader(path).pages]


# ---- Cleaning -----------------------------------------------------------


def clean_text(text: str, context: Optional[str] = None) -> str:
    """Fix what PDF extraction gets wrong, without changing the meaning.

    `context` is the whole document's text; it lets rejoin_hyphenated_words()
    check how a word is written elsewhere. Defaults to `text` itself.
    """
    # NFKC turns look-alike characters into the plain ones: the ligature "ﬁ"
    # becomes "f" + "i", and Arabic letters stored in their joined display
    # shapes become normal Arabic letters.
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("­", "")  # invisible "soft" hyphens
    text = re.sub(r"[ \t]*\.{4,}[ \t]*", " ", text)  # table-of-contents dots
    text = re.sub(r"[ \t]+", " ", text)  # runs of spaces -> one space
    text = re.sub(r" *\n *", "\n", text)  # spaces around line breaks
    text = rejoin_hyphenated_words(text, context)
    text = re.sub(r"\n{3,}", "\n\n", text)  # at most one blank line in a row
    return text.strip()


def rejoin_hyphenated_words(text: str, context: Optional[str] = None) -> str:
    """Join words split across lines: "treat-\\nment" -> "treatment".

    A real compound such as "ankle-foot" keeps its hyphen if the document
    also writes it on one line somewhere.
    """
    written_elsewhere = (text if context is None else context).lower()

    def join(match: re.Match) -> str:
        first, second = match.group(1), match.group(2)
        if f"{first}-{second}".lower() in written_elsewhere:
            return f"{first}-{second}"
        return first + second

    return _HYPHEN_BREAK.sub(join, text)


def drop_references(pages: list[Page]) -> tuple[list[Page], Optional[int], Optional[int]]:
    """Remove the reference list at the end of a document.

    The list runs from the last "References" heading (English, German or
    Arabic) to the end of the document, or to an appendix heading that
    follows it; the appendix is kept. Reference lists are 11-34% of the
    current documents; left in, a search can match the title of a cited
    paper instead of the document's own text.

    Returns the pages kept, the page the references start on, and the page
    the appendix starts on (None when there is no such heading).
    """
    headings = [  # (index into pages, heading match), in document order
        (index, match)
        for index, (_, text) in enumerate(pages)
        for match in _REFERENCES_HEADING.finditer(text)
    ]
    if not headings:
        return pages, None, None

    # Some documents repeat "REFERENCES" as a page header on every page of
    # the list (the WHO standards: pages 71, 73, 75). While the heading is
    # such a header and another heading is at most 2 pages earlier, the list
    # started there.
    first = len(headings) - 1
    while first > 0:
        index, match = headings[first]
        earlier_index, _ = headings[first - 1]
        is_page_header = pages[index][1][: match.start()].count("\n") < 2
        if not is_page_header or pages[index][0] - pages[earlier_index][0] > 2:
            break
        first -= 1
    start_index, heading = headings[first]

    last_index, last_heading = headings[-1]
    end = None  # (index into pages, where the appendix heading starts)
    for index in range(last_index, len(pages)):
        search_from = last_heading.end() if index == last_index else 0
        appendix = _APPENDIX_HEADING.search(pages[index][1], search_from)
        if appendix:
            end = (index, appendix.start())
            break

    number, text = pages[start_index]
    kept = pages[:start_index]
    before = text[: heading.start()].strip()
    if end is None:
        return kept + ([(number, before)] if before else []), number, None

    end_index, appendix_start = end
    end_number, end_text = pages[end_index]
    after = end_text[appendix_start:].strip()
    if end_index == start_index:  # references and appendix start on the same page
        kept.append((number, f"{before}\n\n{after}".strip()))
    else:
        kept += ([(number, before)] if before else []) + [(end_number, after)]
    return kept + pages[end_index + 1 :], number, end_number


def drop_repeated_lines(pages: list[Page]) -> tuple[list[Page], int]:
    """Remove page headers and footers: lines that repeat on many pages.

    Digits are ignored when comparing lines, so "Page 3 of 146" and
    "Page 4 of 146" count as the same line. Left in, a header such as
    "STANDARDS FOR PROSTHETICS AND ORTHOTICS • PART 1" lands in every chunk
    and makes unrelated chunks look alike to the search.

    Returns the cleaned pages and the number of distinct lines removed.
    """

    def key(line: str) -> str:
        return re.sub(r"\d+", "#", line.strip())

    lines_per_page = Counter(
        k for _, text in pages for k in {key(line) for line in text.splitlines()} if k
    )
    threshold = max(3, REPEATED_LINE_SHARE * len(pages))
    repeated = {k for k, count in lines_per_page.items() if count >= threshold}
    if not repeated:
        return pages, 0

    cleaned = []
    for number, text in pages:
        kept = "\n".join(line for line in text.splitlines() if key(line) not in repeated).strip()
        if kept:
            cleaned.append((number, kept))
    return cleaned, len(repeated)


def drop_search_syntax(pages: list[Page]) -> tuple[list[Page], int]:
    """Remove lines of literature-search syntax (a review's search strategy).

    They list every topic word with OR between them, so left in they would
    "match" almost any gap. Returns the cleaned pages and the lines removed.
    """
    cleaned = []
    removed = 0
    for number, text in pages:
        lines = text.splitlines()
        kept = [line for line in lines if len(_SEARCH_SYNTAX.findall(line)) < SEARCH_SYNTAX_PER_LINE]
        removed += len(lines) - len(kept)
        if kept:
            cleaned.append((number, "\n".join(kept)))
    return cleaned, removed


def check_arabic(raw_text: str) -> list[str]:
    """Warnings for an Arabic source whose text may have come out wrong."""
    display_forms = len(_ARABIC_DISPLAY_FORMS.findall(raw_text))
    letters = len(_ARABIC_LETTERS.findall(raw_text)) + display_forms
    if letters < 100:
        return ["almost no Arabic letters found; is this the right file, or a scan?"]
    if display_forms > letters * 0.1:
        return [
            "Arabic letters were stored in their display shapes, so words may "
            "come out reversed. Check the extracted text; if it reads wrong, "
            "use a .txt copy of the document instead."
        ]
    return []


# ---- One document -------------------------------------------------------


def extract_document(doc: SourceDocument, sources_dir: Path = SOURCES_DIR) -> ExtractedDocument:
    raw_pages = read_pages(sources_dir / doc.file)
    warnings = check_arabic("".join(raw_pages)) if doc.language == "ar" else []

    context = unicodedata.normalize("NFKC", "\n".join(raw_pages))
    pages = []
    no_text = []
    for number, raw in enumerate(raw_pages, start=1):
        text = clean_text(raw, context)
        if len(text) < MIN_PAGE_CHARS:
            no_text.append(number)
        if text:
            pages.append((number, text))
    if no_text:
        warnings.append(f"pages with (almost) no text, maybe scanned images: {no_text}")

    pages, repeated_removed = drop_repeated_lines(pages)
    pages, search_removed = drop_search_syntax(pages)
    pages, references_from, appendix_from = drop_references(pages)
    return ExtractedDocument(
        doc,
        pages,
        total_pages=len(raw_pages),
        references_from_page=references_from,
        appendix_from_page=appendix_from,
        repeated_lines_removed=repeated_removed,
        search_lines_removed=search_removed,
        warnings=warnings,
    )


def write_extracted(extracted: ExtractedDocument, out_dir: Path = EXTRACTED_DIR) -> Path:
    """Write data/extracted/<id>.txt: a short header, then each page's text."""
    doc = extracted.document
    lines = [
        f"# id: {doc.id}",
        f"# title: {doc.title}",
        f"# file: {doc.file}",
        f"# language: {doc.language}",
        f"# pages: {extracted.total_pages} in the original; {extracted.references_summary()}",
        f"# page headers/footers: {extracted.repeated_lines_removed} repeated lines removed",
        f"# literature-search syntax: {extracted.search_lines_removed} lines removed",
        "# Generated by `python -m knowledge.extract`. Edits here are overwritten.",
    ]
    for number, text in extracted.pages:
        lines += ["", f"--- page {number} ---", text]

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{doc.id}.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def read_extracted(path: Path) -> list[Page]:
    """The pages back from a file written by write_extracted()."""
    parts = _PAGE_MARKER.split(path.read_text(encoding="utf-8"))
    # parts = [header, "1", text of page 1, "2", text of page 2, ...]
    return [(int(number), text.strip()) for number, text in zip(parts[1::2], parts[2::2])]


# ---- Command line -------------------------------------------------------


def extract_all(
    catalog_path: Path = CATALOG_PATH,
    sources_dir: Path = SOURCES_DIR,
    out_dir: Path = EXTRACTED_DIR,
) -> list[tuple[SourceDocument, Path]]:
    """Extract every catalogued document, printing one line per document.

    Returns (document, extracted text file) for each document extracted.
    Text files of documents no longer in the catalog are deleted.
    """
    documents = load_catalog(catalog_path)
    if not documents:
        print(f"No documents: {catalog_path} is missing or empty. Nothing extracted.")
        return []
    for path in find_unlisted_files(documents, sources_dir, SOURCES_NOT_INGESTED):
        print(f"WARNING not in catalog.json, skipped: {path.relative_to(sources_dir)}")

    written = []
    for doc in documents:
        if not (sources_dir / doc.file).is_file():
            print(f"WARNING file missing, skipped: {doc.file}")
            continue
        extracted = extract_document(doc, sources_dir)
        written.append((doc, write_extracted(extracted, out_dir)))
        characters = sum(len(text) for _, text in extracted.pages)
        print(
            f"{doc.id}: {len(extracted.pages)} of {extracted.total_pages} pages, "
            f"{characters:,} characters, {extracted.references_summary()}"
        )
        for warning in extracted.warnings:
            print(f"  WARNING {warning}")

    current = {doc.id for doc in documents}
    for stale in out_dir.glob("*.txt"):
        if stale.stem not in current:
            stale.unlink()
            print(f"removed {stale.name}: no longer in the catalog")
    return written


def main() -> None:
    extract_all()
    print(f"\nCleaned text is in {EXTRACTED_DIR}")


if __name__ == "__main__":
    main()
