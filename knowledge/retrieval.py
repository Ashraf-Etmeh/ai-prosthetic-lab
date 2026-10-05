"""Protocol retrieval.

v1 thin-slice status: STUBBED. This always returns one hardcoded fake chunk
so intake -> knowledge -> reasoning -> review can run end to end before the
real ingestion pipeline exists. Step 3 replaces this with a real similarity
search over documents ingested from data/sources/ (see knowledge/ingest.py,
added in that step). See FUTURE_WORK.md.
"""

from shared.case_schema import Case
from shared.config import RETRIEVAL_TOP_K

from knowledge.models import ProtocolChunk

_STUB_CHUNK = ProtocolChunk(
    chunk_id="stub-0001",
    text=(
        "[STUB PROTOCOL TEXT] A complete prosthetic evaluation intake should "
        "document residual limb wound status and volume stability, current "
        "activity level, prior device history, and relevant comorbidities "
        "before specialist evaluation."
    ),
    source="stub_protocol.txt",
    score=1.0,
)


def retrieve_relevant_chunks(
    case: Case, top_k: int = RETRIEVAL_TOP_K
) -> list[ProtocolChunk]:
    """Return protocol chunks relevant to this case.

    STUB (step 2): ignores `case` and `top_k`, always returns the same fake
    chunk. Real implementation lands in step 3.
    """
    return [_STUB_CHUNK]
