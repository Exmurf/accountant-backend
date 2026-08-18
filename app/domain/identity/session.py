from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SessionTokens:
    access_token: str
    refresh_token: str
