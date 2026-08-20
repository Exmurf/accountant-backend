import logging
from functools import lru_cache

from redis import Redis
from redis.exceptions import RedisError

from app.application.caching.ports import Cache
from app.core.config import get_settings
from app.infrastructure.cache.null_cache import NullCache
from app.infrastructure.cache.redis_cache import RedisCache

logger = logging.getLogger(__name__)


@lru_cache
def get_cache() -> Cache:
    settings = get_settings()
    if not settings.redis_url:
        return NullCache()

    client = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        # Short on purpose. A cache that hangs is worse than no cache: the
        # request would wait on an optimisation before doing the real work.
        socket_timeout=0.25,
        socket_connect_timeout=0.25,
        retry_on_timeout=False,
    )
    try:
        client.ping()
        logger.info("Cache connected")
    except RedisError as error:
        # Still handed back rather than swapped for a null cache, so a server
        # that was merely slow to start is picked up on the next call instead
        # of leaving the application uncached until someone restarts it.
        logger.warning("Cache unreachable at start-up: %s", error)
    return RedisCache(client, settings.cache_ttl_seconds)
