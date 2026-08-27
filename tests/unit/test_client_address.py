"""Which address a request is charged to when a proxy sits in front.

This is the piece that decides whose quota a request spends. Get it wrong in
one direction and every request behind the proxy shares one budget; get it
wrong in the other and a caller can rotate their own key at will.
"""

import pytest
from starlette.requests import Request

from app.core.config import Settings
from app.presentation.dependencies import rate_limit
from app.presentation.dependencies.rate_limit import client_address, describe_wait

PROXY_NETWORK = "172.16.0.0/12"
PROXY = "172.18.0.5"
CALLER = "203.0.113.9"
FORGED = "6.6.6.6"


@pytest.fixture
def trusting(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    def trust(networks: str) -> None:
        settings = Settings(
            jwt_secret_key="test-only",
            trusted_proxy_ips=networks,
            cookie_secure=False,
            web_origin="http://localhost:3000",
        )
        monkeypatch.setattr(rate_limit, "get_settings", lambda: settings)

    return trust


def make_request(peer: str | None, forwarded: str | None = None) -> Request:
    headers = []
    if forwarded is not None:
        headers.append((b"x-forwarded-for", forwarded.encode()))
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "scheme": "http",
            "query_string": b"",
            "headers": headers,
            "client": None if peer is None else (peer, 51234),
        }
    )


def test_with_no_proxy_configured_the_header_is_ignored(trusting) -> None:  # type: ignore[no-untyped-def]
    """Anyone can send that header. Believing it while the service is reached
    directly would hand every caller a fresh quota per request."""
    trusting("")

    assert client_address(make_request(CALLER, forwarded=FORGED)) == CALLER


def test_a_header_from_a_trusted_proxy_is_believed(trusting) -> None:  # type: ignore[no-untyped-def]
    trusting(PROXY_NETWORK)

    assert client_address(make_request(PROXY, forwarded=CALLER)) == CALLER


def test_the_chain_is_read_from_the_right(trusting) -> None:  # type: ignore[no-untyped-def]
    """Every hop appends what it saw, so anything the caller invented ends up
    to the left of what our own proxy wrote."""
    trusting(PROXY_NETWORK)

    address = client_address(make_request(PROXY, forwarded=f"{FORGED}, {CALLER}"))

    assert address == CALLER


def test_a_chain_of_nothing_but_proxies_falls_back_to_the_peer(trusting) -> None:  # type: ignore[no-untyped-def]
    trusting(PROXY_NETWORK)

    address = client_address(make_request(PROXY, forwarded="172.18.0.6, 172.18.0.7"))

    assert address == PROXY


def test_a_header_from_anyone_else_is_ignored(trusting) -> None:  # type: ignore[no-untyped-def]
    trusting(PROXY_NETWORK)

    assert client_address(make_request(CALLER, forwarded=FORGED)) == CALLER


def test_a_bare_address_may_be_trusted_on_its_own(trusting) -> None:  # type: ignore[no-untyped-def]
    trusting(PROXY)

    assert client_address(make_request(PROXY, forwarded=CALLER)) == CALLER


def test_an_address_next_to_the_trusted_one_is_not_trusted(trusting) -> None:  # type: ignore[no-untyped-def]
    trusting(PROXY)

    assert client_address(make_request("172.18.0.6", forwarded=CALLER)) == "172.18.0.6"


def test_nonsense_in_the_header_is_not_taken_as_an_address(trusting) -> None:  # type: ignore[no-untyped-def]
    trusting(PROXY_NETWORK)

    address = client_address(make_request(PROXY, forwarded="bu-adres-degil"))

    assert address == "bu-adres-degil"


def test_a_request_with_no_peer_at_all_still_gets_a_key(trusting) -> None:  # type: ignore[no-untyped-def]
    trusting("")

    assert client_address(make_request(None)) == "unknown"


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(1, "1 saniye"), (59, "59 saniye"), (60, "1 dakika"), (900, "15 dakika")],
)
def test_the_wait_is_described_in_the_larger_unit(seconds: int, expected: str) -> None:
    assert describe_wait(seconds) == expected
