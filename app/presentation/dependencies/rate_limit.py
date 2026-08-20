from fastapi import HTTPException, Request, status

from app.application.security.ports import RateLimiter
from app.infrastructure.security.rate_limit import InMemoryRateLimiter

# One window shared by every request, so it has to outlive the request scope.
_limiter = InMemoryRateLimiter()


def get_rate_limiter() -> RateLimiter:
    return _limiter


def client_address(request: Request) -> str:
    """The peer address of the connection.

    `X-Forwarded-For` is ignored on purpose. Nothing in front of this service is
    trusted to set it yet, and honouring a header the caller controls would let
    an attacker rotate their own key and walk straight past the limit. Put a
    trusted-proxy list here before running behind a reverse proxy.
    """
    return request.client.host if request.client is not None else "unknown"


def describe_wait(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} saniye"
    return f"{max(1, round(seconds / 60))} dakika"


def enforce(retry_after: int | None, detail: str) -> None:
    if retry_after is None:
        return
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"{detail} {describe_wait(retry_after)} sonra tekrar deneyin.",
        headers={"Retry-After": str(retry_after)},
    )
