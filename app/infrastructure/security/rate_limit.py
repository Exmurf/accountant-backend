import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from math import ceil
from time import monotonic

SWEEP_INTERVAL_SECONDS = 300


@dataclass(slots=True)
class _Bucket:
    window_seconds: int
    hits: deque[float] = field(default_factory=deque)


class InMemoryRateLimiter:
    """Sliding window of attempt timestamps, held in the API process.

    A single process serves the API, so a process-local window is enough. The
    counts are deliberately not persisted: a restart forgives outstanding
    lockouts, which is the safe direction for a mechanism that can shut a real
    user out of their own account.

    A monotonic clock is used rather than the wall clock so a system time change
    cannot stretch or collapse a window.
    """

    def __init__(self, clock: Callable[[], float] = monotonic) -> None:
        self._clock = clock
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()
        self._swept_at = 0.0

    def peek(self, key: str, limit: int, window_seconds: int) -> int | None:
        with self._lock:
            now = self._clock()
            bucket = self._bucket(key, window_seconds, now)
            if len(bucket.hits) < limit:
                return None
            return max(1, ceil(bucket.hits[0] + window_seconds - now))

    def record(self, key: str, window_seconds: int) -> None:
        with self._lock:
            now = self._clock()
            self._bucket(key, window_seconds, now).hits.append(now)
            self._sweep(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._buckets.pop(key, None)

    def _bucket(self, key: str, window_seconds: int, now: float) -> _Bucket:
        bucket = self._buckets.get(key)
        if bucket is None or bucket.window_seconds != window_seconds:
            bucket = _Bucket(window_seconds=window_seconds)
            self._buckets[key] = bucket

        cutoff = now - window_seconds
        while bucket.hits and bucket.hits[0] <= cutoff:
            bucket.hits.popleft()
        return bucket

    def _sweep(self, now: float) -> None:
        """Drop keys nobody has touched, so a scan of many emails cannot grow
        the dictionary without bound."""
        if now - self._swept_at < SWEEP_INTERVAL_SECONDS:
            return
        self._swept_at = now
        for key, bucket in list(self._buckets.items()):
            if not bucket.hits or bucket.hits[-1] <= now - bucket.window_seconds:
                del self._buckets[key]
