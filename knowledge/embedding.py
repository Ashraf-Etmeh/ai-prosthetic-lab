"""Turning text into vectors with the embedding model.

Ingestion and retrieval both go through embed_texts(), so documents and
search queries are always embedded the same way. The model is loaded on
first use and then kept in memory (loading takes several seconds, and
about 2.3 GB on the first run while it downloads).
"""

from contextlib import contextmanager
from functools import lru_cache
from typing import Optional

import numpy as np

from shared.config import EMBEDDING_MAX_TOKENS, EMBEDDING_MODEL_NAME, EMBEDDING_MODEL_REVISION


@contextmanager
def hub_offline():
    """No request to the Hugging Face Hub while this runs (CLAUDE.md principle 3: search stays local).

    `local_files_only` alone is not enough (measured 2026-10-16 with the network
    blocked): huggingface_hub still fetches an "agent registry" from
    huggingface.co when it builds request headers, and transformers starts a
    thread that asks the Hub about a safetensors conversion of a model stored as
    pytorch_model.bin, as bge-m3's pinned revision is. Both check
    huggingface_hub's offline flag when they run, so switching it on here stops
    them, whatever imported huggingface_hub first. The flag is restored
    afterwards, so a model missing from the cache can still be downloaded.
    """
    from huggingface_hub import constants

    before = constants.HF_HUB_OFFLINE
    constants.HF_HUB_OFFLINE = True
    try:
        yield
    finally:
        constants.HF_HUB_OFFLINE = before


@lru_cache(maxsize=2)
def load_model(name: str = EMBEDDING_MODEL_NAME, revision: Optional[str] = EMBEDDING_MODEL_REVISION):
    # Imported here, not at the top: sentence-transformers takes seconds to
    # import, and the tests and the web app's start-up don't need it.
    from sentence_transformers import SentenceTransformer

    # The revision is pinned, so a copy already in the Hugging Face cache is
    # exactly the right one: load it without asking the server. Only a
    # missing model goes to the network (and downloads ~2.3 GB once).
    try:
        with hub_offline():
            model = SentenceTransformer(name, revision=revision, local_files_only=True)
    except OSError:
        model = SentenceTransformer(name, revision=revision)  # uses the GPU if there is one
    model.max_seq_length = EMBEDDING_MAX_TOKENS
    return model


def embed_texts(
    texts: list[str],
    model_name: str = EMBEDDING_MODEL_NAME,
    revision: Optional[str] = EMBEDDING_MODEL_REVISION,
    show_progress: bool = False,
) -> np.ndarray:
    """One row per text, each of length 1, so a dot product is the cosine similarity."""
    model = load_model(model_name, revision)
    vectors = model.encode(
        texts,
        batch_size=16,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=show_progress,
    )
    return vectors.astype(np.float32)
