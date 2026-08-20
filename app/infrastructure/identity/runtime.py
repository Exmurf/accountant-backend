import logging

from app.application.identity.request_password_reset import RequestPasswordReset
from app.core.config import get_settings
from app.infrastructure.database.repositories.password_resets import (
    SqlAlchemyPasswordResetTokenRepository,
)
from app.infrastructure.database.repositories.users import SqlAlchemyUserRepository
from app.infrastructure.database.session import session_factory
from app.infrastructure.mail.addresses import is_placeholder_address
from app.infrastructure.mail.smtp import SmtpMailSender
from app.infrastructure.security.tokens import PasswordResetTokenService

logger = logging.getLogger(__name__)


def deliver_password_reset(email: str) -> None:
    """Run the whole request after the response has gone out.

    Nothing here can reach the caller, which is the point: an address that is
    registered and one that is not must be indistinguishable, including in how
    long the reply took and whether anything failed.
    """
    settings = get_settings()
    if not settings.mail_enabled:
        logger.warning("A password reset was requested while mail is unconfigured")
        return
    if is_placeholder_address(email):
        # A seeded demo account cannot receive the link, so issuing a token for
        # it would only leave an unusable row behind.
        return

    try:
        with session_factory() as session:
            RequestPasswordReset(
                users=SqlAlchemyUserRepository(session),
                reset_tokens=SqlAlchemyPasswordResetTokenRepository(session),
                token_service=PasswordResetTokenService(),
                mailer=SmtpMailSender(settings),
                web_origin=settings.web_origin,
                token_lifetime_minutes=settings.password_reset_token_minutes,
            ).execute(email)
    except Exception:
        logger.exception("Password reset mail could not be sent")
