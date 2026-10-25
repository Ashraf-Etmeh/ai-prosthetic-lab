"""Which build of the source library the search uses (SYSTEM_DESIGN.md §7.1: "each build is a version").

`python -m knowledge.ingest` writes data/knowledge/vector_store/info.json with the
time it was built, the embedding model and the passages per document. That build
time is the library's version: the review log records it with every decision, and
the quality page shows it next to the model and prompt versions.
"""

import json
from pathlib import Path
from typing import Optional

from shared import config


def library_version(store_dir: Optional[Path] = None) -> Optional[dict]:
    """The library build: {"built", "passages", "documents", "model"}; None if it hasn't been built."""
    path = (store_dir or config.VECTOR_STORE_DIR) / "info.json"
    try:
        info = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return {
        "built": info.get("created"),
        "passages": info.get("chunks"),
        "documents": len(info.get("chunks_per_document") or {}),
        "model": info.get("model"),
    }
