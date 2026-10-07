"""Turning text into vectors with the embedding model.

Ingestion and retrieval both go through embed_texts(), so documents and
search queries are always embedded the same way. The model is loaded on
first use and then kept in memory (loading takes several seconds, and
about 2.3 GB on the first run while it downloads).
"""

from functools import lru_cache
from typing import Optional

import numpy as np

from shared.config import EMBEDDING_MAX_TOKENS, EMBEDDING_MODEL_NAME, EMBEDDING_MODEL_REVISION


@lru_cache(maxsize=2)
def load_model(name: str = EMBEDDING_MODEL_NAME, revision: Optional[str] = EMBEDDING_MODEL_REVISION):
    # Imported here, not at the top: sentence-transformers takes seconds to
    # import, and the tests and the web app's start-up don't need it.
    from sentence_transformers import SentenceTransformer

    # The revision is pinned, so a copy already in the Hugging Face cache is
    # exactly the right one: load it without asking the server. Only a
    # missing model goes to the network (and downloads ~2.3 GB once).
    try:
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
