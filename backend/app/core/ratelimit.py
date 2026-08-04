"""A small in-memory rate limiter.

Deliberately process-local: the deployment is a single instance, and pulling in
Redis for two endpoints would be infrastructure for its own sake. If the app
ever scales out, replace this with a shared store — the call sites won't change.
"""

import threading
import time
from collections import deque


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def _prune(self, key: str, window: float, now: float) -> deque[float]:
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= now - window:
            hits.popleft()
        return hits

    def blocked(self, key: str, limit: int, window: float) -> bool:
        """Whether the key has already used up its attempts."""
        with self._lock:
            return len(self._prune(key, window, time.monotonic())) >= limit

    def record(self, key: str, window: float) -> None:
        with self._lock:
            self._prune(key, window, time.monotonic()).append(time.monotonic())

    def clear(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = SlidingWindowLimiter()
