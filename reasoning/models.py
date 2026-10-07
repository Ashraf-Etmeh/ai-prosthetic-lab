"""Data model for one gap-analysis finding.

A Gap describes one piece of information that appears to be missing before
a case is ready for specialist evaluation. It is NOT a treatment or
component recommendation — see shared/config.py DISCLAIMER, which is
attached to every gap list this layer produces.
"""

from dataclasses import dataclass
from typing import Optional

from knowledge.models import ProtocolChunk


@dataclass
class Gap:
    field: str  # dotted Case field path, e.g. "residual_limb.wound_status"
    label: str  # the field's name for the reviewer, e.g. "Residual limb wound status"
    status: str  # "not recorded" or "recorded as unknown"
    why_needed: str  # plain-language reason, pointing at the cited passage
    # chunk_id of the cited passage. Always one of the chunks retrieved for
    # this field, so the specialist can check it. None: no passage found.
    source_protocol_reference: Optional[str] = None
    evidence: Optional[ProtocolChunk] = None  # the cited passage itself
    excerpt: Optional[str] = None  # its sentences that mention this field's topic
