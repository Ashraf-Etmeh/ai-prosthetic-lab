"""Data model for a retrieved protocol chunk.

This is intentionally separate from the ingestion/storage implementation
(step 3) so the reasoning layer can depend on a stable shape regardless of
whether the chunk came from Chroma, FAISS, or a hardcoded stub.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ProtocolChunk:
    chunk_id: str
    text: str
    source: str  # filename the chunk came from, e.g. "va_dod_cpg_2022.txt"
    score: Optional[float] = None  # similarity score, if the retriever set one
