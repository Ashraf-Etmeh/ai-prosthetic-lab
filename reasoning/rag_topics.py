"""The topics of a case's RAG: what is searched, and what the model is asked about.

Shared by every domain: a Topic, and the "gaps" part (one topic per missing
intake field, shared/field_guide.py, with the field guide's own search text).
Each domain adds its other parts and their topics (prosthetics/topics.py,
orthotics/topics.py), found through shared/domains.py.
"""

from dataclasses import dataclass

from shared import domains
from shared.case_schema import CaseCore

GAPS = "gaps"


@dataclass(frozen=True)
class Topic:
    key: str  # a gap's field path, a component or fitting section key, or "functional_level"
    part: str  # GAPS or one of the domain's parts
    label: str  # English, for the model
    query: str  # the search text


def topics_for_case(case: CaseCore) -> list[Topic]:
    """Every topic of the case, part by part, in the order the review page shows them."""
    return domains.part(case.domain, "topics").topics_for_case(case)
