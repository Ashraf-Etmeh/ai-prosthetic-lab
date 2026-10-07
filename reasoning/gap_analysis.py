"""Gap analysis: case + retrieved passages -> list of information gaps.

Rules, not a language model: a model call would be a cloud service (out of
scope for v1), and language models often cite sources that don't support
what they say (Wu et al. 2025, data/sources/04_ai_safety_regulation).

For each missing field (shared/field_guide.py: empty, or recorded as
unknown), in the field guide's order:
1. Go through the passages retrieved for that field, best score first.
2. Cite the first one that passes two checks:
   - its similarity score is at least MIN_RELEVANCE_SCORE, and
   - it mentions the field's topic (FieldInfo.topic_terms, in the
     passage's own language).
3. Quote that passage's sentences on the topic. The reason a field matters
   is then the source's own words, which the specialist can check.
4. If no passage passes, the gap is still listed, saying that no source
   was found, instead of citing a weak one.

IMPORTANT: this layer produces information-gap findings only. It must never
phrase output as a diagnosis, a treatment choice, or a component
recommendation. Every item is a suggestion for specialist review.
"""

import re
from typing import Optional

from knowledge.models import ProtocolChunk
from reasoning.models import Gap
from shared.case_schema import Case
from shared.config import MIN_RELEVANCE_SCORE
from shared.field_guide import NOT_RECORDED, FieldInfo, MissingField, missing_fields

MAX_EXCERPT_SENTENCES = 2
MAX_EXCERPT_CHARS = 400
# A longer "sentence" is usually a table row or a title block; only the
# part around the topic words is shown.
MAX_SENTENCE_CHARS = 250

_SENTENCE_END = re.compile(r"(?<=[.!?؟])\s+")


def analyze_gaps(
    case: Case,
    retrieved: dict[str, list[ProtocolChunk]],
    min_score: float = MIN_RELEVANCE_SCORE,
) -> list[Gap]:
    """One Gap per missing field. `retrieved` maps field paths to passages."""
    return [
        _make_gap(missing, retrieved.get(missing.info.path, []), min_score)
        for missing in missing_fields(case)
    ]


def find_evidence(
    info: FieldInfo, chunks: list[ProtocolChunk], min_score: float = MIN_RELEVANCE_SCORE
) -> Optional[tuple[ProtocolChunk, str]]:
    """The best passage that passes both checks, and its excerpt. None if none does."""
    for chunk in sorted(chunks, key=lambda c: c.score or 0.0, reverse=True):
        if chunk.score is None or chunk.score < min_score:
            break  # sorted, so no later chunk scores higher
        excerpt = topic_excerpt(info, chunk)
        if excerpt:
            return chunk, excerpt
    return None


def topic_excerpt(info: FieldInfo, chunk: ProtocolChunk) -> Optional[str]:
    """The chunk's first sentences that mention the field's topic, or None.

    Sentences that weren't next to each other in the chunk are joined
    with " … " to show that text was left out.
    """
    sentences = _SENTENCE_END.split(chunk.text)
    hits = []  # (sentence index, the part of it to show)
    for index, sentence in enumerate(sentences):
        span = info.topic_span(sentence, chunk.language)
        if span is not None:
            hits.append((index, _around(sentence, span)))
        if len(hits) == MAX_EXCERPT_SENTENCES:
            break
    if not hits:
        return None
    excerpt = hits[0][1]
    for (previous, _), (index, part) in zip(hits, hits[1:]):
        excerpt += (" " if index == previous + 1 else " … ") + part
    if len(excerpt) > MAX_EXCERPT_CHARS:
        excerpt = excerpt[:MAX_EXCERPT_CHARS].rsplit(" ", 1)[0] + " …"
    return excerpt


def _around(sentence: str, span: tuple[int, int]) -> str:
    """The sentence, or for a long one the words around `span`, marked with "…"."""
    if len(sentence) <= MAX_SENTENCE_CHARS:
        return sentence
    room = max(0, MAX_SENTENCE_CHARS - (span[1] - span[0])) // 2
    start = max(0, span[0] - room)
    end = min(len(sentence), span[1] + room)
    # Move inward to whole words, but never into the topic words themselves.
    if start > 0:
        space = sentence.find(" ", start, span[0])
        if space != -1:
            start = space + 1
    if end < len(sentence):
        space = sentence.rfind(" ", span[1], end)
        if space != -1:
            end = space
    before = "… " if start > 0 else ""
    after = " …" if end < len(sentence) else ""
    return before + sentence[start:end].strip() + after


def _make_gap(missing: MissingField, chunks: list[ProtocolChunk], min_score: float) -> Gap:
    info = missing.info
    if missing.status == NOT_RECORDED:
        opening = f"{info.label} was not recorded at intake."
    else:
        opening = f"{info.label} was recorded as unknown."

    found = find_evidence(info, chunks, min_score)
    if found is None:
        return Gap(
            field=info.path,
            label=info.label,
            status=missing.status,
            why_needed=(
                f"{opening} No passage in the source library was found on this "
                "topic, so whether it is needed is for the specialist to judge."
            ),
        )

    evidence, excerpt = found
    return Gap(
        field=info.path,
        label=info.label,
        status=missing.status,
        why_needed=(
            f"{opening} {evidence.citation} discusses this topic (quoted below); "
            "check whether it applies to this case."
        ),
        source_protocol_reference=evidence.chunk_id,
        evidence=evidence,
        excerpt=excerpt,
    )
