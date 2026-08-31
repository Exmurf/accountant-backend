from functools import lru_cache
from ipaddress import IPv4Network, IPv6Network, ip_network

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env",),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    web_origin: str = "http://localhost:3000"
    # Addresses or CIDR blocks whose `X-Forwarded-For` may be believed. Empty
    # means nothing is trusted, which is right whenever the service is reached
    # directly. Behind a reverse proxy, name the proxy here.
    trusted_proxy_ips: str = ""
    database_url: str = (
        "postgresql+psycopg://accountant:accountant_dev_password"
        "@localhost:5432/accountant"
    )

    jwt_secret_key: str
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    cookie_secure: bool = False
    app_timezone: str = "Europe/Istanbul"

    rate_limit_enabled: bool = True
    login_max_attempts: int = Field(default=5, ge=1)
    login_ip_max_attempts: int = Field(default=30, ge=1)
    login_window_seconds: int = Field(default=900, ge=1)
    register_max_attempts: int = Field(default=5, ge=1)
    register_window_seconds: int = Field(default=3600, ge=1)
    password_reset_max_attempts: int = Field(default=3, ge=1)
    password_reset_ip_max_attempts: int = Field(default=10, ge=1)
    password_reset_window_seconds: int = Field(default=3600, ge=1)
    password_reset_token_minutes: int = Field(default=60, ge=1)
    email_change_max_attempts: int = Field(default=3, ge=1)
    email_change_window_seconds: int = Field(default=3600, ge=1)
    email_change_token_minutes: int = Field(default=60, ge=1)

    redis_url: str = ""
    cache_ttl_seconds: int = Field(default=300, ge=1)

    mail_username: str = ""
    mail_app_password: str = ""
    mail_from_name: str = "Accountant"
    mail_smtp_host: str = "smtp.gmail.com"
    mail_smtp_port: int = Field(default=587, ge=1, le=65535)
    daily_summary_catchup_days: int = Field(default=3, ge=0, le=31)

    @model_validator(mode="after")
    def _reject_unusable_cookie_scheme(self) -> "Settings":
        """Refuse a secure cookie on a plain-HTTP origin.

        The browser would never send the cookie back, so every login would
        appear to succeed and then be forgotten. It is the shape a development
        env file takes when it reaches a server, and a startup failure is far
        cheaper to read than that symptom.
        """
        if self.cookie_secure and self.web_origin.startswith("http://"):
            raise ValueError(
                "COOKIE_SECURE is on but WEB_ORIGIN is plain http, so no session "
                "cookie would ever come back. Serve the site over https, or turn "
                "COOKIE_SECURE off for local work."
            )
        return self

    @property
    def mail_enabled(self) -> bool:
        return bool(self.mail_username and self.mail_app_password)

    @property
    def trusted_proxies(self) -> tuple[IPv4Network | IPv6Network, ...]:
        """`trusted_proxy_ips` as networks. A bare address becomes a /32 or /128.

        Unparseable entries are dropped rather than raised: a typo here should
        narrow what is trusted, never keep the application from starting.
        """
        networks = []
        for entry in self.trusted_proxy_ips.split(","):
            entry = entry.strip()
            if not entry:
                continue
            try:
                networks.append(ip_network(entry, strict=False))
            except ValueError:
                continue
        return tuple(networks)


@lru_cache
def get_settings() -> Settings:
    return Settings()
