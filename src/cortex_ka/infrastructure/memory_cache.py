"""In-memory fallback cache adapter (used for local dev/testing)."""

from __future__ import annotations

from ..domain.ports import CachePort


class InMemoryCache(CachePort):
    """Simple dictionary-based cache for development when Redis unavailable."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def get_answer(self, query: str) -> str | None:
        return self._store.get(query)

    def set_answer(self, query: str, answer: str) -> None:
        self._store[query] = answer
