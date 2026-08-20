from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.database.models.identity import PasswordResetTokenModel


class SqlAlchemyPasswordResetTokenRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def replace_for_user(
        self,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
        now: datetime,
    ) -> None:
        """Issue a token and retire whatever the user already had.

        Asking again is how somebody recovers from a link that never arrived,
        so every request must work; leaving the older links alive would mean a
        forwarded mail from an hour ago still opens the account.
        """
        outstanding = self._session.scalars(
            select(PasswordResetTokenModel)
            .where(
                PasswordResetTokenModel.user_id == user_id,
                PasswordResetTokenModel.used_at.is_(None),
            )
            .with_for_update()
        ).all()
        for token in outstanding:
            token.used_at = now

        self._session.add(
            PasswordResetTokenModel(
                user_id=user_id,
                token_hash=token_hash,
                expires_at=expires_at,
            )
        )
        self._session.commit()

    def consume(self, token_hash: str, now: datetime) -> UUID | None:
        """Spend the token, returning its owner only if it was still good.

        Marking it used in the same transaction that reads it means two
        requests carrying the same link cannot both succeed.
        """
        token = self._session.scalar(
            select(PasswordResetTokenModel)
            .where(PasswordResetTokenModel.token_hash == token_hash)
            .with_for_update()
        )
        if token is None or token.used_at is not None or token.expires_at <= now:
            self._session.rollback()
            return None

        token.used_at = now
        self._session.commit()
        return token.user_id
