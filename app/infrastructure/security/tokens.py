import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from app.core.config import Settings


class JwtTokenService:
    algorithm = "HS256"

    def __init__(self, settings: Settings) -> None:
        self._secret = settings.jwt_secret_key
        self._lifetime = timedelta(minutes=settings.access_token_minutes)

    def create(self, user_id: UUID) -> str:
        now = datetime.now(UTC)
        return jwt.encode(
            {
                "sub": str(user_id),
                "iat": now,
                "exp": now + self._lifetime,
            },
            self._secret,
            algorithm=self.algorithm,
        )

    def decode_subject(self, token: str) -> UUID:
        payload = jwt.decode(token, self._secret, algorithms=[self.algorithm])
        return UUID(payload["sub"])


class OpaqueRefreshTokenService:
    def create(self) -> str:
        return secrets.token_urlsafe(64)

    def hash(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
