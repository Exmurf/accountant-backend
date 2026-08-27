"""Settings that refuse to start rather than fail quietly later."""

from ipaddress import ip_network

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def build(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "jwt_secret_key": "test-only",
        "cookie_secure": False,
        "web_origin": "http://localhost:3000",
    }
    return Settings(**{**defaults, **overrides})  # type: ignore[arg-type]


def test_a_secure_cookie_on_a_plain_http_origin_is_refused() -> None:
    """The browser would never send the cookie back, so every sign-in would
    look like it worked and then be forgotten. That is the shape a development
    env file takes when it reaches a server, and it is far cheaper to read as a
    startup failure than as that symptom."""
    with pytest.raises(ValidationError, match="COOKIE_SECURE"):
        build(cookie_secure=True, web_origin="http://accountant.mail.dev")


def test_a_secure_cookie_over_https_is_the_expected_case() -> None:
    settings = build(cookie_secure=True, web_origin="https://accountant.mail.dev")

    assert settings.cookie_secure is True


def test_plain_http_without_a_secure_cookie_is_how_local_work_runs() -> None:
    assert build(cookie_secure=False, web_origin="http://localhost:3000").cookie_secure is False


def test_trusting_nothing_is_the_default() -> None:
    assert build().trusted_proxies == ()


def test_a_bare_address_becomes_a_single_host_network() -> None:
    assert build(trusted_proxy_ips="10.0.0.7").trusted_proxies == (
        ip_network("10.0.0.7/32"),
    )


def test_several_networks_may_be_listed() -> None:
    settings = build(trusted_proxy_ips="10.0.0.0/8, 192.168.0.0/16")

    assert settings.trusted_proxies == (
        ip_network("10.0.0.0/8"),
        ip_network("192.168.0.0/16"),
    )


def test_a_typo_narrows_what_is_trusted_rather_than_stopping_the_service() -> None:
    """Dropping the unreadable entry errs towards trusting less, which is the
    safe direction; refusing to start would take the whole site down over a
    stray character."""
    settings = build(trusted_proxy_ips="10.0.0.0/8, bu-bir-ag-degil, 172.16.0.0/12")

    assert settings.trusted_proxies == (
        ip_network("10.0.0.0/8"),
        ip_network("172.16.0.0/12"),
    )


def test_mail_is_only_on_when_both_halves_are_configured() -> None:
    assert build(mail_username="a@mail.dev", mail_app_password="gizli").mail_enabled
    assert not build(mail_username="a@mail.dev", mail_app_password="").mail_enabled
    assert not build(mail_username="", mail_app_password="gizli").mail_enabled
