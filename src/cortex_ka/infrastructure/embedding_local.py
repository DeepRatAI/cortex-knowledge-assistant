"""Local sentence-transformers embedding adapter."""

from __future__ import annotations

from sentence_transformers import SentenceTransformer

from ..config import settings
from ..domain.ports import EmbedderPort


class LocalEmbedder(EmbedderPort):
    """Uses a local sentence-transformers model for embeddings."""

    def __init__(self) -> None:
        self._model = SentenceTransformer(settings.embedding_model)

    def embed(self, texts):  # type: ignore[override]
        return self._model.encode(list(texts), convert_to_numpy=True).tolist()
