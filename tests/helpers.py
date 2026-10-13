"""Shared test helpers: tiny stand-ins for the embedding model and the AI writer.

The real model is 2.3 GB and slow to load, so tests use fake_embed: each
word adds 1 to one of 64 positions, then the vector is scaled to length 1.
Texts sharing words get similar vectors, which is all the tests need.

The Claude API is never called in tests (tests/__init__.py switches it off);
FakeWriter answers instead, without any network.
"""

import re
import zlib

import numpy as np

from reasoning.writer import WriterResult, WriterUnavailable

DIMENSIONS = 64

# A passage as reasoning/rag.py user_message() writes it for the model.
_PASSAGE = re.compile(r'<passage id="([^"]+)"[^>]*found_for="([^"]*)">\n(.*?)\n</passage>', re.DOTALL)


def quote_every_topic(user: str, schema: dict, words: int = 8) -> dict:
    """An answer with one item per topic asked: the first `words` words of a passage found for it.

    The sentences name the topic ("AI sentence about knee."), so a test can
    find them on the page.
    """
    item = schema["properties"]["items"]["items"]["properties"]
    passages = [(chunk_id, topics.split(", "), text) for chunk_id, topics, text in _PASSAGE.findall(user)]
    items = []
    for topic in item["topic"]["enum"]:
        chunk_id, _, text = next(p for p in passages if topic in p[1])
        items.append({"topic": topic, "passage_id": chunk_id, "quote": " ".join(text.split()[:words]),
                      "sentence_en": f"AI sentence about {topic}.", "sentence_ar": f"جملة الذكاء الاصطناعي عن {topic}.",
                      "grade": ""})
    return {"items": items}


class FakeWriter:
    """Answers like the Claude API would, without any network.

    answer: a dict (the same answer every time), a function (user, schema) ->
    dict, or None: quote_every_topic. error: raise WriterUnavailable(error).
    Every call is kept in .calls as (system, user, schema).
    """

    def __init__(self, answer=None, error: str | None = None, name: str = "fake-model"):
        self.name = name
        self.answer = answer
        self.error = error
        self.calls: list[tuple[str, str, dict]] = []

    def write(self, system: str, user: str, schema: dict) -> WriterResult:
        self.calls.append((system, user, schema))
        if self.error:
            raise WriterUnavailable(self.error)
        if callable(self.answer):
            data = self.answer(user, schema)
        else:
            data = self.answer if self.answer is not None else quote_every_topic(user, schema)
        return WriterResult(data=data, model=self.name, usage={"input_tokens": 100, "output_tokens": 50},
                            seconds=0.1)


def fake_embed(texts: list[str]) -> np.ndarray:
    vectors = np.zeros((len(texts), DIMENSIONS), dtype=np.float32)
    for row, text in enumerate(texts):
        for word in re.findall(r"\w+", text.lower()):
            vectors[row, zlib.crc32(word.encode()) % DIMENSIONS] += 1
    lengths = np.linalg.norm(vectors, axis=1, keepdims=True)
    lengths[lengths == 0] = 1
    return vectors / lengths


def chunk_record(
    chunk_id: str, text: str, domains=("prosthetics",), language: str = "en", page: int = 1, limbs=None
) -> dict:
    """One chunk as knowledge/ingest.py stores it in chunks.json."""
    doc_id = chunk_id.rsplit("-", 1)[0]
    return {
        "chunk_id": chunk_id,
        "doc_id": doc_id,
        "text": text,
        "source": f"01_guidelines/{doc_id}.pdf",
        "title": f"Title of {doc_id}",
        "year": 2024,
        "page": page,
        "end_page": page,
        "language": language,
        "domains": list(domains),
        "limbs": None if limbs is None else list(limbs),
        "source_type": "protocol",
    }
