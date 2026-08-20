from typing import Protocol


class Cache(Protocol):
    """A cache the application can lose at any moment without being wrong.

    Every method is allowed to do nothing. A read may always miss and a write
    may always be dropped, so a caller must treat this as an optimisation and
    never as a place data lives.
    """

    def read(self, namespace: str, key: str) -> str | None: ...

    def write(self, namespace: str, key: str, payload: str) -> None: ...

    def invalidate(self, namespace: str) -> None:
        """Forget everything under one namespace."""
        ...

    def invalidate_everything(self) -> None:
        """Forget every namespace at once."""
        ...
