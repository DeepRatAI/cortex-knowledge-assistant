"""In-memory conversation store and rate limiter for development.

These implementations are process-local and suitable for unit tests and local dev.
In production, replace with Redis-backed state.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque, Dict, List, Tuple


class RateLimiter:
    """Token-bucket-like limiter.

    Supports both global and keyed (API key or session) limits. Uses a sliding
    window of 60 seconds.
    """

    def __init__(self, qpm: int) -> None:
        self.capacity = max(1, qpm)
        self.window = 60.0
        self.events: Deque[float] = deque()
        self.key_events: Dict[str, Deque[float]] = defaultdict(deque)  # keyed buckets

    def _purge(self, bucket: Deque[float]) -> None:
        now = time.time()
        while bucket and now - bucket[0] > self.window:
            bucket.popleft()

    def allow(self, key: str | None = None) -> bool:
        """Return True if allowed under global and keyed quota.

        Global bucket controls total throughput. Per-key bucket allows isolation so
        one noisy key does not starve others prematurely.
        """
        now = time.time()
        # Keyed mode: only enforce per-key quota for independence
        if key is not None:
            bucket = self.key_events[key]
            self._purge(bucket)
            # Check per-key first
            if len(bucket) >= self.capacity:
                return False
            bucket.append(now)
            return True
        # Global (unkeyed) mode
        self._purge(self.events)
        # No key: just global control
        if len(self.events) >= self.capacity:
            return False
        self.events.append(now)
        return True


class ConversationMemory:
    """Stores last N turns of a conversation keyed by session id."""

    def __init__(self, max_turns: int = 5) -> None:
        self.max_turns = max_turns
        self._store: Dict[str, Deque[Tuple[str, str]]] = defaultdict(lambda: deque(maxlen=self.max_turns))

    def add_turn(self, session_id: str, user: str, assistant: str) -> None:
        self._store[session_id].append((user, assistant))

    def history(self, session_id: str) -> List[Tuple[str, str]]:
        return list(self._store.get(session_id, deque()))
