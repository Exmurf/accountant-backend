class NullCache:
    """What the application uses when no cache is configured.

    Reads miss, writes vanish. Keeping this rather than scattering `if cache`
    checks means the uncached path is the same code path as the cached one, so
    it cannot rot while nobody is looking at it.
    """

    def read(self, namespace: str, key: str) -> str | None:
        return None

    def write(self, namespace: str, key: str, payload: str) -> None:
        return None

    def invalidate(self, namespace: str) -> None:
        return None

    def invalidate_everything(self) -> None:
        return None
