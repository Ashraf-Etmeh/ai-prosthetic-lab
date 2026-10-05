"""The source catalog: which documents the knowledge layer uses, and what they are.

data/sources/catalog.json is written by hand (its fields are explained in
data/sources/README.md). This module loads it and checks every entry, so a
typo fails loudly here instead of turning up later in search results.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from shared.config import CATALOG_PATH

# Allowed values. Keep in sync with data/sources/README.md.
SOURCE_TYPES = frozenset({
    "protocol",
    "scientific_reference",
    "professional_knowledge",
    "applied_case",
    "structured_data",
    "specialist_expertise",
})
DOMAINS = frozenset({"prosthetics", "orthotics", "gait", "rehabilitation"})
LANGUAGES = frozenset({"en", "ar", "de"})
FILE_TYPES = frozenset({".pdf", ".txt"})


@dataclass
class SourceDocument:
    id: str  # permanent: chunk ids are built from it
    file: str  # path relative to the folder holding catalog.json
    title: str
    authors: str
    year: int
    publisher: str
    source_type: str
    domains: list[str]
    language: str
    doi: Optional[str] = None
    url: Optional[str] = None
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        if self.source_type not in SOURCE_TYPES:
            raise ValueError(f"{self.id}: unknown source_type {self.source_type!r}")
        if not self.domains or not set(self.domains) <= DOMAINS:
            raise ValueError(f"{self.id}: domains must be from {sorted(DOMAINS)}, got {self.domains!r}")
        if self.language not in LANGUAGES:
            raise ValueError(f"{self.id}: unknown language {self.language!r}")
        if Path(self.file).suffix.lower() not in FILE_TYPES:
            raise ValueError(f"{self.id}: file must be .pdf or .txt, got {self.file!r}")


def load_catalog(catalog_path: Path = CATALOG_PATH) -> list[SourceDocument]:
    """Every document in the catalog. An empty list if there is no catalog yet.

    Raises ValueError for a bad entry (unknown value, misspelled or missing
    field, repeated id).
    """
    if not catalog_path.is_file():
        return []
    entries = json.loads(catalog_path.read_text(encoding="utf-8"))["documents"]

    documents = []
    for number, entry in enumerate(entries, start=1):
        try:
            documents.append(SourceDocument(**entry))
        except TypeError as error:  # a field is misspelled or missing
            raise ValueError(f"catalog entry {number} ({entry.get('id')}): {error}") from None

    ids = [doc.id for doc in documents]
    repeated = sorted({i for i in ids if ids.count(i) > 1})
    if repeated:
        raise ValueError(f"catalog ids used more than once: {repeated}")
    return documents


def find_unlisted_files(documents: list[SourceDocument], sources_dir: Path) -> list[Path]:
    """.pdf and .txt files under sources_dir that the catalog doesn't list."""
    listed = {doc.file for doc in documents}
    return sorted(
        path
        for path in sources_dir.rglob("*")
        if path.suffix.lower() in FILE_TYPES
        and path.relative_to(sources_dir).as_posix() not in listed
    )
