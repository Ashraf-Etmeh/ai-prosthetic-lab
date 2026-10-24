"""What each case field means for the knowledge and reasoning layers: the mechanics.

Each domain lists its own fields (prosthetics/fields.py, orthotics/fields.py: `FIELDS`);
this module holds what they share and finds a case's list through shared/domains.py.

For every intake field that can be an information gap, this says:
- `label`: the name the reviewer sees,
- `query`: what retrieval searches the source library for when the field
  is missing (English; the multilingual model also finds Arabic and German
  passages),
- `topic_terms`: words, per language, that a passage must contain to be
  cited for this field. A passage can score as "similar" without being
  about the field; this check stops a gap from citing an off-topic source.

Order matters: gaps are shown to the reviewer in this order.
Free-text note fields (`residual_limb.notes`, `intake_notes`) are not
listed, so an empty note is never reported as a gap.
"""

import re
from dataclasses import dataclass
from collections.abc import Iterator, Mapping
from typing import Optional

from shared import domains
from shared.case_schema import CaseCore

NOT_RECORDED = "not recorded"
RECORDED_UNKNOWN = "recorded as unknown"

# Arabic short vowels, shadda, sukun and tatweel. Removed before matching
# topic terms, so "الجِلد" matches the term "الجلد".
_ARABIC_MARKS = re.compile("[ـً-ْٰ]")


@dataclass(frozen=True)
class FieldInfo:
    path: str  # dotted Case field path, as in Case.unrecorded_fields()
    label: str
    query: str
    topic_terms: dict[str, str]  # language code -> regular expression
    # Orthotics only, a PROPOSAL awaiting the owner (2026-10-22): information the
    # orthotist needs before weighing an orthosis. The page marks such a gap; it
    # hides nothing. Prosthetic fields are never marked.
    critical: bool = False

    def topic_span(self, text: str, language: str) -> Optional[tuple[int, int]]:
        """(start, end) of the first topic term in `text`, or None."""
        pattern = self.topic_terms.get(language)
        if pattern is None:
            return None
        # Match on the text without Arabic vowel marks, but report positions
        # in the original text: kept[i] is where stripped character i came from.
        kept = [i for i, char in enumerate(text) if not _ARABIC_MARKS.match(char)]
        match = re.search(pattern, "".join(text[i] for i in kept), re.IGNORECASE)
        if match is None:
            return None
        return kept[match.start()], kept[match.end() - 1] + 1

    def mentions_topic(self, text: str, language: str) -> bool:
        return self.topic_span(text, language) is not None


@dataclass(frozen=True)
class MissingField:
    info: FieldInfo
    status: str  # NOT_RECORDED or RECORDED_UNKNOWN


class _AllFields(Mapping):
    """Every domain's fields by path, for labels. A core path (age, comorbidities, ...) is in
    several domains' lists with the same label: the first domain's entry names it. Built on
    first use, because the domains' field guides import this module."""

    def __init__(self) -> None:
        self._by_path: Optional[dict[str, FieldInfo]] = None

    def _all(self) -> dict[str, FieldInfo]:
        if self._by_path is None:
            by_path: dict[str, FieldInfo] = {}
            for domain in domains.DOMAINS:
                for info in domains.part(domain, "fields").FIELDS:
                    by_path.setdefault(info.path, info)
            self._by_path = by_path
        return self._by_path

    def __getitem__(self, path: str) -> FieldInfo:
        return self._all()[path]

    def __iter__(self) -> Iterator[str]:
        return iter(self._all())

    def __len__(self) -> int:
        return len(self._all())


FIELDS_BY_PATH: Mapping[str, FieldInfo] = _AllFields()


def fields_for(case) -> tuple[FieldInfo, ...]:
    """The gap fields of the case's domain."""
    return domains.part(case.domain, "fields").FIELDS


def missing_fields(case: CaseCore) -> list[MissingField]:
    """The case's information gaps, in its field guide's order: empty or 'unknown' fields."""
    unrecorded = set(case.unrecorded_fields())
    unknown = set(case.unknown_fields())
    missing = []
    for info in fields_for(case):
        if info.path in unrecorded:
            missing.append(MissingField(info, NOT_RECORDED))
        elif info.path in unknown:
            missing.append(MissingField(info, RECORDED_UNKNOWN))
    return missing


def build_query(case: CaseCore, info: FieldInfo) -> str:
    """The search text for one missing field, as the case's domain words it (its fields.py query_for)."""
    return domains.part(case.domain, "fields").query_for(case, info)
