"""A quoted statement with what the source catalog says about its document (title, year, language, kind)."""

from functools import lru_cache
from typing import Optional

from knowledge.catalog import load_catalog
from reasoning.models import CitedStatement, GuidelineStatement


@lru_cache(maxsize=1)
def _documents() -> dict[str, tuple[str, Optional[int], str, str]]:
    """Catalog id -> (title, year, language, source type)."""
    return {doc.id: (doc.title, doc.year, doc.language, doc.source_type) for doc in load_catalog()}


def cite(statement: GuidelineStatement) -> CitedStatement:
    return CitedStatement(statement, *_documents()[statement.doc_id])
