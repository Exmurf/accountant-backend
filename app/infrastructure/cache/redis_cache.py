import logging

from redis import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

GLOBAL_VERSION_KEY = "accountant:version"


class RedisCache:
    """Cache entries keyed by a version that a write bumps rather than deletes.

    Deleting everything a user touched would mean scanning the keyspace for a
    pattern, which Redis walks key by key and warns against on anything but a
    toy. A version folded into the key turns invalidation into one INCR: the
    next read looks under a number nothing was ever written to, and the
    orphaned entries fall out on their own when their time expires.

    Every call is allowed to fail. Redis is not the source of truth here, so a
    refused connection has to cost a query rather than an error page.
    """

    def __init__(self, client: Redis, ttl_seconds: int) -> None:
        self._client = client
        self._ttl_seconds = ttl_seconds
        self._unreachable = False

    def read(self, namespace: str, key: str) -> str | None:
        try:
            value = self._client.get(self._full_key(namespace, key))
        except RedisError as error:
            self._note_failure("read", error)
            return None
        self._note_recovery()
        return value if value is None else str(value)

    def write(self, namespace: str, key: str, payload: str) -> None:
        try:
            self._client.set(
                self._full_key(namespace, key),
                payload,
                ex=self._ttl_seconds,
            )
        except RedisError as error:
            self._note_failure("write", error)
            return
        self._note_recovery()

    def invalidate(self, namespace: str) -> None:
        try:
            self._client.incr(self._version_key(namespace))
        except RedisError as error:
            # Serving stale entries until they expire beats failing the write
            # that triggered this, so the error stops here.
            self._note_failure("invalidation", error)
            return
        self._note_recovery()

    def invalidate_everything(self) -> None:
        try:
            self._client.incr(GLOBAL_VERSION_KEY)
        except RedisError as error:
            self._note_failure("global invalidation", error)
            return
        self._note_recovery()

    def _note_failure(self, action: str, error: RedisError) -> None:
        """One line per outage, not one per call.

        A cache this size is touched several times a request, so logging each
        refused connection with a traceback would bury every real error in the
        file under thousands of copies of the same one.
        """
        if self._unreachable:
            return
        self._unreachable = True
        logger.warning("Cache unreachable, serving uncached (%s): %s", action, error)

    def _note_recovery(self) -> None:
        if not self._unreachable:
            return
        self._unreachable = False
        logger.info("Cache reachable again")

    def _full_key(self, namespace: str, key: str) -> str:
        """Both versions in one round trip, so a hit costs two calls, not three."""
        overall, local = self._client.mget(
            [GLOBAL_VERSION_KEY, self._version_key(namespace)]
        )
        return f"{namespace}:g{overall or '0'}:v{local or '0'}:{key}"

    @staticmethod
    def _version_key(namespace: str) -> str:
        return f"{namespace}:version"
