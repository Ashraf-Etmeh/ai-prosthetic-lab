"""Gap analysis: case + retrieved protocol chunks -> structured gap list.

v1 thin-slice status: STUBBED. This always returns one hardcoded fake gap so
intake -> knowledge -> reasoning -> review can run end to end before the
real reasoning logic exists. Step 4 replaces this with real logic driven by
`case.unrecorded_fields()` and the retrieved chunks. See FUTURE_WORK.md.

IMPORTANT: this layer produces information-gap findings only. It must never
phrase output as a diagnosis, a treatment choice, or a component
recommendation. Every item is a suggestion for specialist review.
"""

from shared.case_schema import Case

from knowledge.models import ProtocolChunk
from reasoning.models import Gap

_STUB_GAP = Gap(
    field="residual_limb.wound_status",
    why_needed=(
        "[STUB] Wound status must be documented before specialist evaluation "
        "can proceed."
    ),
    source_protocol_reference="stub_protocol.txt",
)


def analyze_gaps(case: Case, chunks: list[ProtocolChunk]) -> list[Gap]:
    """Return the list of information gaps for this case.

    STUB (step 2): ignores `case` and `chunks`, always returns the same fake
    gap. Real implementation lands in step 4.
    """
    return [_STUB_GAP]
