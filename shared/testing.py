"""What every part's tests share: the AI switched off, and tiny stand-ins for the model, the writer and the app.

Each part keeps its tests in <part>/tests/; each of those packages imports this
module first, so importing it switches the AI writer (Gemini or Claude API) off
for every test: `python -m unittest` (and `python -m unittest <part>.tests.test_x`)
can't reach the API, even on a machine where an API key is set
(reasoning/writer.py default_writer() then returns a writer that is always
unavailable). Tests that need answers pass a FakeWriter.

The real model is 2.3 GB and slow to load, so tests use fake_embed: each
word adds 1 to one of 64 positions, then the vector is scaled to length 1.
Texts sharing words get similar vectors, which is all the tests need.
"""

import html
import os
import re
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

import numpy as np

from shared import config
from shared.config import OFFLINE_ENV

os.environ[OFFLINE_ENV] = "1"

from reasoning.writer import WriterResult, WriterUnavailable  # noqa: E402  (after the switch above)
from shared.store import store  # noqa: E402

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


def visible_text(page: str) -> str:
    """The page without its HTML tags, entities and bidi isolate marks: roughly what a reader sees."""
    return html.unescape(re.sub(r"<[^>]+>|[\u2068\u2069]", "", page))


def no_passages(case) -> dict:
    """A search that finds nothing (RouteTestCase's default; each domain's tests give their own)."""
    return {}


class RouteTestCase(unittest.TestCase):
    """The app through Flask's test client: a fake AI writer, a stand-in for the search, and a temporary
    review log and case folder, never the real data/records/.

    `fake_retrieval` stands in for knowledge/retrieval.py retrieve_relevant_chunks (the 2.3 GB model is
    never loaded): each domain's route tests set their own passages (prosthetics/tests/helpers.py).
    """

    fake_retrieval = staticmethod(no_passages)

    def setUp(self):
        from app import create_app  # here: only the route tests need the whole app

        app = create_app()
        app.testing = True
        # The AI: a fake that quotes the passages it is given, never the API.
        self.writer = FakeWriter()
        app.config["RAG_WRITER"] = self.writer
        self.app = app
        self.client = app.test_client()
        retrieval = patch("reasoning.pathway.retrieve_relevant_chunks", side_effect=self.fake_retrieval)
        retrieval.start()
        self.addCleanup(retrieval.stop)
        # Decisions go to a temporary log, never to the real data/records/review_log.jsonl,
        # and cases to a temporary folder, never to the real data/records/cases/.
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.log_path = Path(tmp.name) / "review_log.jsonl"
        log_path = patch("review.decision_log.REVIEW_LOG_PATH", self.log_path)
        log_path.start()
        self.addCleanup(log_path.stop)
        self.cases_dir = Path(tmp.name) / "cases"
        cases_dir = patch.object(store, "folder", self.cases_dir)
        cases_dir.start()
        self.addCleanup(cases_dir.stop)
        # Learning attempts, the learning log and the teaching cases' analyses, never the real
        # data/records/learning/ (search/learning.py).
        learning_dir = patch.object(config, "LEARNING_DIR", Path(tmp.name) / "learning")
        learning_dir.start()
        self.addCleanup(learning_dir.stop)
        # People's records and the access trail, never the real data/records/people/ and access_log.jsonl
        # (record/people.py, record/access.py).
        for name, value in (("PEOPLE_DIR", Path(tmp.name) / "people"),
                            ("ACCESS_LOG_PATH", Path(tmp.name) / "access_log.jsonl")):
            patcher = patch.object(config, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
