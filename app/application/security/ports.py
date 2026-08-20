from typing import Protocol


class RateLimiter(Protocol):
    def peek(self, key: str, limit: int, window_seconds: int) -> int | None:
        """Seconds left on the key's lockout, or None while it still has quota."""
        ...

    def record(self, key: str, window_seconds: int) -> None:
        """Count one attempt against the key."""
        ...

    def reset(self, key: str) -> None:
        """Forget every attempt recorded for the key."""
        ...
