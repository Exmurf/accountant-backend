import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from app.core.config import Settings
from app.domain.identity.session import AccessTokenClaims


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

    def decode(self, token: str) -> AccessTokenClaims:
        payload = jwt.decode(token, self._secret, algorithms=[self.algorithm])
        return AccessTokenClaims(
            user_id=UUID(payload["sub"]),
            issued_at=datetime.fromtimestamp(payload["iat"], UTC),
        )


class OpaqueTokenService:
    """A random secret the server only ever keeps the digest of, so a leaked
    table cannot be replayed against the API."""

    token_bytes = 64

    def create(self) -> str:
        return secrets.token_urlsafe(self.token_bytes)

    def hash(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()


class OpaqueRefreshTokenService(OpaqueTokenService):
    pass


class EmailChangeTokenService(OpaqueTokenService):
    token_bytes = 48


class PasswordResetTokenService(OpaqueTokenService):
    # This one travels in a link and is occasionally copied by hand, so it is
    # shorter than a refresh token while staying far outside guessing range.
    token_bytes = 48
