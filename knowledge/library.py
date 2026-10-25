"""The source library as the knowledge pages show it (SYSTEM_DESIGN.md §7.1; plan Parts 4-5, 2026-10-25).

- library_version(): which build of the library the search uses. `python -m
  knowledge.ingest` writes data/knowledge/vector_store/info.json with the time it
  was built, the embedding model and the passages per document. That build time
  is the library's version: the review log records it with every decision, and
  the quality and source pages show it.
- library_rows(): every document the project knows, with its kind, language,
  licence as recorded ("not shown" when none), what extraction did to its text
  (from the header of data/knowledge/extracted/<id>.txt) and its status: searched
  (catalogued and in the search index), catalogued but not in the index, link only
  (the registry could not download it), or downloaded but not catalogued (never
  quoted: only what is catalogued can be quoted).
- curator_queue(): what needs a curator, from those facts and the recorded results.

Facts only: nothing here judges a source's quality or evidence.
"""

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from shared import config

SOURCES_MANIFEST = config.SOURCES_DIR / "00_registry" / "sources_manifest.csv"
# A page with less text than this is counted as "almost no text" (a figure, a divider or a scan).
THIN_PAGE_CHARS = 80
SEARCHED, NOT_IN_INDEX, LINK_ONLY, NOT_CATALOGUED = "searched", "not_in_index", "link_only", "not_catalogued"
STATUSES = (SEARCHED, NOT_IN_INDEX, LINK_ONLY, NOT_CATALOGUED)
NEEDS_DOWNLOAD = "needs manual download"  # the registry's status


def _store_info(store_dir: Optional[Path] = None) -> Optional[dict]:
    path = (store_dir or config.VECTOR_STORE_DIR) / "info.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def library_version(store_dir: Optional[Path] = None) -> Optional[dict]:
    """The library build: {"built", "passages", "documents", "model"}; None if it hasn't been built."""
    info = _store_info(store_dir)
    if info is None:
        return None
    return {
        "built": info.get("created"),
        "passages": info.get("chunks"),
        "documents": len(info.get("chunks_per_document") or {}),
        "model": info.get("model"),
    }


@dataclass(frozen=True)
class TextFacts:
    """What extraction recorded about a document's text (the header of its extracted file)."""

    pages: Optional[int] = None  # pages in the original
    references_from: Optional[int] = None  # the page the removed references start on
    header_lines: Optional[int] = None  # repeated page headers and footers removed
    search_lines: Optional[int] = None  # literature-search syntax lines removed
    thin_pages: int = 0  # pages left with almost no text
    split_words: bool = False  # split ligatures rejoined (catalog "split_ligatures")


def _number(pattern: str, header: str) -> Optional[int]:
    found = re.search(pattern, header, re.MULTILINE)
    return int(found.group(1)) if found else None


def text_facts(doc_id: str, split_words: bool = False, extracted_dir: Optional[Path] = None) -> Optional[TextFacts]:
    """The extracted text's facts; None if the document has no extracted text."""
    path = (extracted_dir or config.EXTRACTED_DIR) / f"{doc_id}.txt"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    header = "\n".join(line for line in text.splitlines()[:12] if line.startswith("# "))
    pages = re.split(r"^--- page \d+ ---$", text, flags=re.MULTILINE)[1:]
    return TextFacts(
        pages=_number(r"^# pages: (\d+)", header),
        references_from=_number(r"references from page (\d+)", header),
        header_lines=_number(r"^# page headers/footers: (\d+)", header),
        search_lines=_number(r"^# literature-search syntax: (\d+)", header),
        thin_pages=sum(1 for page in pages if len(page.strip()) < THIN_PAGE_CHARS),
        split_words=split_words,
    )


@dataclass(frozen=True)
class LibraryRow:
    title: str
    status: str  # one of STATUSES
    doc_id: Optional[str] = None  # the catalog id (None: not catalogued)
    year: Optional[int] = None
    source_type: Optional[str] = None  # the catalog's kind (None: not catalogued)
    language: Optional[str] = None
    licence: Optional[str] = None  # as recorded; None: not shown
    domains: tuple[str, ...] = ()
    facts: Optional[TextFacts] = None
    passages: Optional[int] = None  # in the search index
    excluded_from_gaps: bool = False  # left out of the gap search (config RETRIEVAL_EXCLUDED_DOCUMENTS)


def _manifest(path: Optional[Path] = None) -> list[dict]:
    try:
        with (path or SOURCES_MANIFEST).open(encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    except OSError:
        return []


def library_rows(catalog=None, manifest_path: Optional[Path] = None, store_dir: Optional[Path] = None,
                 extracted_dir: Optional[Path] = None) -> list[LibraryRow]:
    """The catalogued documents (catalog order), then the registry's link-only and uncatalogued ones."""
    from knowledge.catalog import load_catalog  # here: the catalog's checks run only when the page asks

    catalog = load_catalog() if catalog is None else catalog
    indexed = (_store_info(store_dir) or {}).get("chunks_per_document") or {}
    rows = []
    for doc in catalog:
        rows.append(LibraryRow(
            doc.title, SEARCHED if doc.id in indexed else NOT_IN_INDEX, doc.id, doc.year, doc.source_type,
            doc.language, doc.licence, tuple(doc.domains),
            text_facts(doc.id, doc.split_ligatures, extracted_dir), indexed.get(doc.id),
            doc.id in config.RETRIEVAL_EXCLUDED_DOCUMENTS))
    catalogued = {Path(doc.file).name for doc in catalog}
    for entry in _manifest(manifest_path):
        if entry.get("filename") in catalogued or entry.get("folder", "").split("/")[0] in config.SOURCES_NOT_INGESTED:
            continue
        licence = entry.get("licence") or None
        status = LINK_ONLY if entry.get("status") == NEEDS_DOWNLOAD else NOT_CATALOGUED
        rows.append(LibraryRow(entry.get("title", ""), status, licence=None if licence == "not shown" else licence))
    return rows


def curator_queue(rows: list[LibraryRow], search_runs: list[dict], library: Optional[dict]) -> list[dict]:
    """What needs a curator: {"what" (an interface text key under "curate."), "params"}."""
    queue = []
    for row in rows:
        if row.doc_id and row.facts is None:
            queue.append({"what": "not_extracted", "params": {"title": row.title}})
        elif row.status == NOT_IN_INDEX:
            queue.append({"what": "not_in_index", "params": {"title": row.title}})
        if row.status == LINK_ONLY:
            queue.append({"what": "link_only", "params": {"title": row.title}})
    if library and library.get("built"):
        last = search_runs[-1] if search_runs else None
        if last is None or (last.get("recorded_at") or "") < library["built"]:
            queue.append({"what": "search_quality_due", "params": {"built": library["built"][:10]}})
    return queue
