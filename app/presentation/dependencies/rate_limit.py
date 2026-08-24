from functools import lru_cache
from ipaddress import IPv4Network, IPv6Network, ip_address

from fastapi import HTTPException, Request, status

from app.application.security.ports import RateLimiter
from app.core.config import get_settings
from app.infrastructure.security.rate_limit import InMemoryRateLimiter

# One window shared by every request, so it has to outlive the request scope.
_limiter = InMemoryRateLimiter()


def get_rate_limiter() -> RateLimiter:
    return _limiter


# Bounded on purpose: the addresses asked about include forwarded ones, which
# the caller chooses, so an unbounded cache would be theirs to grow.
@lru_cache(maxsize=1024)
def _is_trusted(peer: str, proxies: tuple[IPv4Network | IPv6Network, ...]) -> bool:
    """Whether `peer` sits inside one of the trusted networks.

    Cached because it runs on every limited request and the answer only changes
    when the configuration does.
    """
    if not proxies:
        return False
    try:
        address = ip_address(peer)
    except ValueError:
        return False
    return any(address in network for network in proxies)


def client_address(request: Request) -> str:
    """The address a request is charged to.

    `X-Forwarded-For` counts only when the connection itself comes from a proxy
    named in `TRUSTED_PROXY_IPS`. Anyone can send that header, so believing it
    unconditionally would let a caller rotate their own key and walk straight
    past the limit.

    The header is read from the right, not the left. Every hop appends the address
    it saw, so anything the caller invented ends up to the left of what our own
    proxy wrote; the rightmost address that is not itself a proxy is the caller.
    """
    peer = request.client.host if request.client is not None else "unknown"
    proxies = get_settings().trusted_proxies
    if not _is_trusted(peer, proxies):
        return peer
    forwarded = request.headers.get("x-forwarded-for", "")
    for hop in reversed([hop.strip() for hop in forwarded.split(",")]):
        if hop and not _is_trusted(hop, proxies):
            return hop
    return peer


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
