"""The sliding window that guards signing in.

The limiter takes its clock as an argument, which is what makes a fifteen
minute window testable in microseconds.
"""

from app.infrastructure.security.rate_limit import InMemoryRateLimiter

LIMIT = 5
WINDOW = 900


class FakeClock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def spend(limiter: InMemoryRateLimiter, key: str, times: int) -> None:
    for _ in range(times):
        limiter.record(key, WINDOW)


def test_there_is_quota_left_until_the_limit_is_reached() -> None:
    limiter = InMemoryRateLimiter(FakeClock())

    spend(limiter, "login:ahmet", LIMIT - 1)

    assert limiter.peek("login:ahmet", LIMIT, WINDOW) is None


def test_the_limit_locks_the_key_for_the_rest_of_the_window() -> None:
    clock = FakeClock()
    limiter = InMemoryRateLimiter(clock)

    spend(limiter, "login:ahmet", LIMIT)

    assert limiter.peek("login:ahmet", LIMIT, WINDOW) == WINDOW


def test_the_wait_shrinks_as_the_window_slides() -> None:
    clock = FakeClock()
    limiter = InMemoryRateLimiter(clock)
    spend(limiter, "login:ahmet", LIMIT)

    clock.advance(300)

    assert limiter.peek("login:ahmet", LIMIT, WINDOW) == WINDOW - 300


def test_the_oldest_attempt_falling_out_gives_the_quota_back() -> None:
    """A window, not a counter: waiting is what clears it, and nobody has to
    remember to reset anything."""
    clock = FakeClock()
    limiter = InMemoryRateLimiter(clock)
    spend(limiter, "login:ahmet", LIMIT)

    clock.advance(WINDOW + 1)

    assert limiter.peek("login:ahmet", LIMIT, WINDOW) is None


def test_the_wait_is_never_reported_as_zero() -> None:
    """Zero would read as "try again now" to a caller who then immediately
    fails again."""
    clock = FakeClock()
    limiter = InMemoryRateLimiter(clock)
    spend(limiter, "login:ahmet", LIMIT)

    clock.advance(WINDOW - 0.1)

    assert limiter.peek("login:ahmet", LIMIT, WINDOW) == 1


def test_keys_are_counted_apart() -> None:
    limiter = InMemoryRateLimiter(FakeClock())

    spend(limiter, "login:ahmet", LIMIT)

    assert limiter.peek("login:baskasi", LIMIT, WINDOW) is None


def test_a_successful_attempt_can_hand_the_quota_back_early() -> None:
    limiter = InMemoryRateLimiter(FakeClock())
    spend(limiter, "login:ahmet", LIMIT)

    limiter.reset("login:ahmet")

    assert limiter.peek("login:ahmet", LIMIT, WINDOW) is None


def test_forgetting_a_key_nobody_touched_is_harmless() -> None:
    limiter = InMemoryRateLimiter(FakeClock())

    limiter.reset("login:hicbiri")

    assert limiter.peek("login:hicbiri", LIMIT, WINDOW) is None


def test_keys_nobody_has_touched_are_swept_away() -> None:
    """A scan across many addresses would otherwise leave a bucket behind for
    every one of them."""
    clock = FakeClock()
    limiter = InMemoryRateLimiter(clock)
    for index in range(50):
        limiter.record(f"login:{index}", WINDOW)

    clock.advance(WINDOW + 1)
    limiter.record("login:sonuncu", WINDOW)

    assert list(limiter._buckets) == ["login:sonuncu"]
