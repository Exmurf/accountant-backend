"""The production rate limiter shares its window through Redis."""

import os
from collections.abc import Iterator
from time import sleep
from uuid import uuid4

import pytest
from redis import Redis

from app.infrastructure.security.rate_limit import RedisRateLimiter

TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL")

pytestmark = pytest.mark.skipif(
    not TEST_REDIS_URL,
    reason="TEST_REDIS_URL is required for Redis integration tests",
)


@pytest.fixture
def redis_client() -> Iterator[Redis]:
    client = Redis.from_url(str(TEST_REDIS_URL), decode_responses=True)
    try:
        yield client
    finally:
        client.close()


@pytest.fixture
def prefix(redis_client: Redis):  # type: ignore[no-untyped-def]
    value = f"accountant:test-rate-limit:{uuid4().hex}:"
    yield value
    keys = list(redis_client.scan_iter(f"{value}*"))
    if keys:
        redis_client.delete(*keys)


def test_two_instances_share_the_same_window(
    redis_client: Redis,
    prefix: str,
) -> None:
    first = RedisRateLimiter(redis_client, prefix=prefix)
    second = RedisRateLimiter(redis_client, prefix=prefix)

    first.record("register:ip:203.0.113.10", 60)
    second.record("register:ip:203.0.113.10", 60)

    wait = second.peek("register:ip:203.0.113.10", 2, 60)
    assert wait is not None
    assert 1 <= wait <= 60


def test_reset_is_visible_to_every_instance(
    redis_client: Redis,
    prefix: str,
) -> None:
    first = RedisRateLimiter(redis_client, prefix=prefix)
    second = RedisRateLimiter(redis_client, prefix=prefix)
    key = "login:email:ahmet@example.com"
    first.record(key, 60)

    second.reset(key)

    assert first.peek(key, 1, 60) is None


def test_an_expired_window_returns_its_quota(
    redis_client: Redis,
    prefix: str,
) -> None:
    limiter = RedisRateLimiter(redis_client, prefix=prefix)
    limiter.record("password:user:1", 1)
    assert limiter.peek("password:user:1", 1, 1) is not None

    sleep(1.05)

    assert limiter.peek("password:user:1", 1, 1) is None
