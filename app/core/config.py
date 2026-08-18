from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env",),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_port: int = 3001
    web_origin: str = "http://localhost:3000"
    database_url: str = (
        "postgresql+psycopg://accountant:accountant_dev_password"
        "@localhost:5432/accountant"
    )

    jwt_secret_key: str
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    cookie_secure: bool = False
    app_timezone: str = "Europe/Istanbul"

    mail_username: str = ""
    mail_app_password: str = ""
    mail_from_name: str = "Accountant"
    mail_smtp_host: str = "smtp.gmail.com"
    mail_smtp_port: int = Field(default=587, ge=1, le=65535)
    daily_summary_hour: int = Field(default=21, ge=0, le=23)
    daily_summary_minute: int = Field(default=0, ge=0, le=59)

    @property
    def mail_enabled(self) -> bool:
        return bool(self.mail_username and self.mail_app_password)


@lru_cache
def get_settings() -> Settings:
    return Settings()
