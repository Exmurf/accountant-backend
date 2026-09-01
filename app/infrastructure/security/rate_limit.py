import logging
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from math import ceil
from time import monotonic
from uuid import uuid4

from redis import Redis
from redis.exceptions import RedisError

SWEEP_INTERVAL_SECONDS = 300
REDIS_KEY_PREFIX = "accountant:rate-limit:"

logger = logging.getLogger(__name__)

_PEEK_SCRIPT = """
local now_parts = redis.call('TIME')
local now_ms = (tonumber(now_parts[1]) * 1000) + math.floor(tonumber(now_parts[2]) / 1000)
local limit = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local cutoff = now_ms - window_ms

redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', cutoff)
local count = redis.call('ZCARD', KEYS[1])
if count < limit then
    return -1
end

local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
local remaining_ms = tonumber(oldest[2]) + window_ms - now_ms
return math.max(1, math.ceil(remaining_ms / 1000))
"""

_RECORD_SCRIPT = """
local now_parts = redis.call('TIME')
local now_ms = (tonumber(now_parts[1]) * 1000) + math.floor(tonumber(now_parts[2]) / 1000)
local window_ms = tonumber(ARGV[1])
local cutoff = now_ms - window_ms

redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', cutoff)
redis.call('ZADD', KEYS[1], now_ms, ARGV[2])
redis.call('PEXPIRE', KEYS[1], window_ms)
return 1
"""


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


class RedisRateLimiter:
    """A shared sliding window, with a local safety net during Redis outages.

    Redis server time is used so several API processes cannot disagree because
    their host clocks drift. Each bucket expires after its newest attempt, so
    old addresses disappear without a keyspace scan.

    If Redis becomes temporarily unreachable, requests still have a local
    quota instead of the protection silently switching off. Redis remains the
    shared source while it is healthy.
    """

    def __init__(
        self,
        client: Redis,
        *,
        prefix: str = REDIS_KEY_PREFIX,
        fallback: InMemoryRateLimiter | None = None,
    ) -> None:
        self._client = client
        self._prefix = prefix
        self._fallback = fallback or InMemoryRateLimiter()
        self._peek_script = client.register_script(_PEEK_SCRIPT)
        self._record_script = client.register_script(_RECORD_SCRIPT)
        self._unreachable = False

    def peek(self, key: str, limit: int, window_seconds: int) -> int | None:
        try:
            result = int(
                self._peek_script(
                    keys=[self._full_key(key)],
                    args=[limit, window_seconds * 1000],
                )
            )
        except RedisError as error:
            self._note_failure("check", error)
            return self._fallback.peek(key, limit, window_seconds)

        self._note_recovery()
        self._fallback.reset(key)
        return None if result < 0 else result

    def record(self, key: str, window_seconds: int) -> None:
        try:
            self._record_script(
                keys=[self._full_key(key)],
                args=[window_seconds * 1000, uuid4().hex],
            )
        except RedisError as error:
            self._note_failure("record", error)
            self._fallback.record(key, window_seconds)
            return
        self._note_recovery()
        self._fallback.reset(key)

    def reset(self, key: str) -> None:
        self._fallback.reset(key)
        try:
            self._client.delete(self._full_key(key))
        except RedisError as error:
            self._note_failure("reset", error)
            return
        self._note_recovery()

    def _full_key(self, key: str) -> str:
        return f"{self._prefix}{key}"

    def _note_failure(self, action: str, error: RedisError) -> None:
        if self._unreachable:
            return
        self._unreachable = True
        logger.warning(
            "Rate-limit Redis unreachable, using local fallback (%s): %s",
            action,
            error,
        )

    def _note_recovery(self) -> None:
        if not self._unreachable:
            return
        self._unreachable = False
        logger.info("Rate-limit Redis reachable again")
