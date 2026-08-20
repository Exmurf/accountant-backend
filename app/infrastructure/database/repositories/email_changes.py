from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.identity.email_change import PendingEmailChange
from app.infrastructure.database.models.identity import EmailChangeTokenModel


class SqlAlchemyEmailChangeTokenRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def replace_for_user(
        self,
        user_id: UUID,
        new_email: str,
        token_hash: str,
        expires_at: datetime,
        now: datetime,
    ) -> None:
        """Issue a token and retire any the user was already holding.

        Someone who mistyped an address asks again with the corrected one, and
        the abandoned link must not still be able to move the account to the
        address they got wrong.
        """
        outstanding = self._session.scalars(
            select(EmailChangeTokenModel)
            .where(
                EmailChangeTokenModel.user_id == user_id,
                EmailChangeTokenModel.used_at.is_(None),
            )
            .with_for_update()
        ).all()
        for token in outstanding:
            token.used_at = now

        self._session.add(
            EmailChangeTokenModel(
                user_id=user_id,
                new_email=new_email,
                token_hash=token_hash,
                expires_at=expires_at,
            )
        )
        self._session.commit()

    def consume(self, token_hash: str, now: datetime) -> PendingEmailChange | None:
        """Spend the token, returning what it asked for only if it was good."""
        token = self._session.scalar(
            select(EmailChangeTokenModel)
            .where(EmailChangeTokenModel.token_hash == token_hash)
            .with_for_update()
        )
        if token is None or token.used_at is not None or token.expires_at <= now:
            self._session.rollback()
            return None

        token.used_at = now
        pending = PendingEmailChange(
            user_id=token.user_id,
            new_email=token.new_email,
        )
        self._session.commit()
        return pending
