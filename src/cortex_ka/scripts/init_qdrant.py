"""Qdrant collection initialization script.

Creates (idempotently) the primary collection used for document chunks. This script
is intended to be invoked manually (e.g., `python -m cortex_ka.scripts.init_qdrant`)
or wired into a Makefile task during environment bootstrap.

The collection uses a single named vector "text" with cosine similarity. Adjust the
vector size to match the embedding model in use.
"""

from __future__ import annotations

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from sentence_transformers import SentenceTransformer

from cortex_ka.config import settings
from cortex_ka.logging import logger


def _embedding_dim() -> int:
    model = SentenceTransformer(settings.embedding_model)
    return model.get_sentence_embedding_dimension()


def ensure_collection() -> None:
    dim = _embedding_dim()
    client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)
    name = settings.qdrant_collection_docs

    # Use modern collection API; handle both existence check styles for compatibility.
    try:
        exists = client.collection_exists(name)  # type: ignore[attr-defined]
    except AttributeError:  # pragma: no cover - for older clients
        exists = name in [c.name for c in client.get_collections().collections]

    if exists:
        logger.info("qdrant_collection_exists", name=name)
        return

    # Named vector configuration (single vector called "text"), aligned with
    # QdrantRetriever which queries NamedVector(name="text", ...).
    vectors_config = {"text": VectorParams(size=dim, distance=Distance.COSINE)}

    client.create_collection(collection_name=name, vectors_config=vectors_config)
    logger.info("qdrant_collection_created", name=name, dim=dim)


if __name__ == "__main__":  # pragma: no cover - script entry
    ensure_collection()
