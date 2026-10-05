"""Text extraction: source documents -> cleaned text, page by page.

The first half of ingestion (step 3). For every document in
data/sources/catalog.json, this pulls the text out of the PDF (or .txt),
cleans it, and writes it to data/extracted/<id>.txt. Open those files to see
exactly what the system reads. Chunking and embedding (knowledge/ingest.py,
not yet written) start from these files.

Run:  python -m knowledge.extract

Running it again overwrites data/extracted/, so hand edits there are lost.
"""

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pypdf import PdfReader

from knowledge.catalog import SourceDocument, find_unlisted_files, load_catalog
from shared.config import CATALOG_PATH, EXTRACTED_DIR, SOURCES_DIR

# pypdf logs hundreds of harmless "fontTools is required" warnings.
logging.getLogger("pypdf").setLevel(logging.ERROR)

MIN_PAGE_CHARS = 50  # a page with less text than this is probably a scanned image

_REFERENCES_HEADING = re.compile(
    r"^\s*(references|bibliography|literature cited)\s*$", re.IGNORECASE | re.MULTILINE
)
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
    warnings: list[str] = field(default_factory=list)


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


def drop_references(pages: list[Page]) -> tuple[list[Page], Optional[int]]:
    """Remove everything from the last "References" heading to the end.

    Returns the pages kept and the page number the references started on
    (None if there is no such heading). Reference lists are 11-34% of the
    current documents; left in, a search can match the title of a cited
    paper instead of the document's own text.
    """
    for index in range(len(pages) - 1, -1, -1):
        number, text = pages[index]
        headings = list(_REFERENCES_HEADING.finditer(text))
        if headings:
            before = text[: headings[-1].start()].strip()
            kept = pages[:index] + ([(number, before)] if before else [])
            return kept, number
    return pages, None


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

    pages, references_from = drop_references(pages)
    return ExtractedDocument(doc, pages, len(raw_pages), references_from, warnings)


def write_extracted(extracted: ExtractedDocument, out_dir: Path = EXTRACTED_DIR) -> Path:
    """Write data/extracted/<id>.txt: a short header, then each page's text."""
    doc = extracted.document
    if extracted.references_from_page is None:
        references = "no references heading found"
    else:
        references = f"references from page {extracted.references_from_page} on removed"
    lines = [
        f"# id: {doc.id}",
        f"# title: {doc.title}",
        f"# file: {doc.file}",
        f"# language: {doc.language}",
        f"# pages: {extracted.total_pages} in the original; {references}",
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


def main() -> None:
    documents = load_catalog(CATALOG_PATH)
    if not documents:
        print(f"No documents: {CATALOG_PATH} is missing or empty. Nothing extracted.")
        return
    for path in find_unlisted_files(documents, SOURCES_DIR):
        print(f"WARNING not in catalog.json, skipped: {path.relative_to(SOURCES_DIR)}")

    for doc in documents:
        if not (SOURCES_DIR / doc.file).is_file():
            print(f"WARNING file missing, skipped: {doc.file}")
            continue
        extracted = extract_document(doc)
        write_extracted(extracted)
        characters = sum(len(text) for _, text in extracted.pages)
        if extracted.references_from_page is None:
            references = "no references heading"
        else:
            references = f"references cut from page {extracted.references_from_page}"
        print(
            f"{doc.id}: {len(extracted.pages)} of {extracted.total_pages} pages, "
            f"{characters:,} characters, {references}"
        )
        for warning in extracted.warnings:
            print(f"  WARNING {warning}")
    print(f"\nCleaned text is in {EXTRACTED_DIR}")


if __name__ == "__main__":
    main()
