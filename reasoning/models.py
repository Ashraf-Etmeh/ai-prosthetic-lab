"""Data model for one gap-analysis finding.

A Gap describes one piece of information that appears to be missing before
a case is ready for specialist evaluation. It is NOT a treatment or
component recommendation — see shared/config.py DISCLAIMER, which is
attached to every gap list this layer produces.
"""

from dataclasses import dataclass


@dataclass
class Gap:
    field: str  # dotted Case field path, e.g. "residual_limb.wound_status"
    why_needed: str  # plain-language reason this matters for evaluation
    source_protocol_reference: str  # which protocol/chunk this reasoning came from
