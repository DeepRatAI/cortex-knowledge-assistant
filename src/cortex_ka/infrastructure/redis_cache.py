"""Redis cache adapter implementation."""

from __future__ import annotations

import redis

from ..config import settings
from ..domain.ports import CachePort


class RedisCache(CachePort):
    """Redis-backed cache implementation."""

    def __init__(self) -> None:
        self._client = redis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)

    def get_answer(self, query: str) -> str | None:
        return self._client.get(f"cka:answer:{query}")

    def set_answer(self, query: str, answer: str) -> None:
        self._client.setex(f"cka:answer:{query}", 3600, answer)
