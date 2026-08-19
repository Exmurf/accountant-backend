from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.database.models.identity import RefreshTokenModel


class SqlAlchemyRefreshTokenRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, user_id: UUID, token_hash: str, expires_at: datetime) -> None:
        self._session.add(
            RefreshTokenModel(
                user_id=user_id,
                token_hash=token_hash,
                expires_at=expires_at,
            )
        )
        self._session.commit()

    def rotate(
        self,
        token_hash: str,
        replacement_hash: str,
        replacement_expires_at: datetime,
        now: datetime,
    ) -> UUID | None:
        current = self._session.scalar(
            select(RefreshTokenModel)
            .where(RefreshTokenModel.token_hash == token_hash)
            .with_for_update()
        )
        if (
            current is None
            or current.revoked_at is not None
            or current.expires_at <= now
        ):
            self._session.rollback()
            return None

        replacement = RefreshTokenModel(
            user_id=current.user_id,
            token_hash=replacement_hash,
            expires_at=replacement_expires_at,
        )
        self._session.add(replacement)
        self._session.flush()
        current.revoked_at = now
        current.replaced_by = replacement.id
        self._session.commit()
        return current.user_id

    def revoke_all_for_user(self, user_id: UUID, now: datetime) -> None:
        tokens = self._session.scalars(
            select(RefreshTokenModel)
            .where(
                RefreshTokenModel.user_id == user_id,
                RefreshTokenModel.revoked_at.is_(None),
            )
            .with_for_update()
        ).all()
        for token in tokens:
            token.revoked_at = now
        self._session.commit()

    def revoke(self, token_hash: str, now: datetime) -> None:
        current = self._session.scalar(
            select(RefreshTokenModel)
            .where(RefreshTokenModel.token_hash == token_hash)
            .with_for_update()
        )
        if current is not None and current.revoked_at is None:
            current.revoked_at = now
            self._session.commit()
            return
        self._session.rollback()
