from functools import lru_cache

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
