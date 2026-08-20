import logging

from app.application.identity.change_email import (
    announce_address_change,
    warn_previous_address,
)
from app.application.identity.request_password_reset import RequestPasswordReset
from app.core.config import get_settings
from app.domain.identity.user import User
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


def deliver_email_change_warning(user: User, new_email: str) -> None:
    """Warn the address being left behind, after the response has gone out.

    Like every other mail the application sends on its own, a refused SMTP
    connection is written to the log and goes no further: the caller has already
    been answered, and the confirmation link they need was sent before this.
    """
    settings = get_settings()
    if not settings.mail_enabled:
        return
    try:
        warn_previous_address(SmtpMailSender(settings), user, new_email)
    except Exception:
        logger.exception("Email change warning could not be sent")


def deliver_email_change_notice(user: User, previous_email: str) -> None:
    """Tell the old address the move is done, after the response has gone out.

    The address has already changed by the time this runs, so failing here must
    not be mistaken for the change itself failing.
    """
    settings = get_settings()
    if not settings.mail_enabled:
        return
    try:
        announce_address_change(SmtpMailSender(settings), user, previous_email)
    except Exception:
        logger.exception("Email change notice could not be sent")
