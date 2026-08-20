from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from app.application.identity.ports import (
    PasswordResetTokenRepository,
    RefreshTokenService,
    UserRepository,
)
from app.application.notifications.message import MailAction, MailMessage
from app.application.notifications.ports import MailSender


class RequestPasswordReset:
    """Mail a one-time link to whoever owns the address, if anyone does.

    Nothing about the outcome reaches the caller. Telling them whether the
    address is registered would turn this endpoint into a way to find out who
    holds an account here, which is exactly what it must not become.
    """

    def __init__(
        self,
        users: UserRepository,
        reset_tokens: PasswordResetTokenRepository,
        token_service: RefreshTokenService,
        mailer: MailSender,
        web_origin: str,
        token_lifetime_minutes: int,
    ) -> None:
        self._users = users
        self._reset_tokens = reset_tokens
        self._token_service = token_service
        self._mailer = mailer
        self._web_origin = web_origin.rstrip("/")
        self._token_lifetime_minutes = token_lifetime_minutes

    def execute(self, email: str) -> bool:
        user = self._users.get_by_email(email.strip().lower())
        if user is None or not user.is_active:
            return False

        now = datetime.now(UTC)
        token = self._token_service.create()
        self._reset_tokens.replace_for_user(
            user_id=user.id,
            token_hash=self._token_service.hash(token),
            expires_at=now + timedelta(minutes=self._token_lifetime_minutes),
            now=now,
        )

        # Only the digest was stored, so this is the one moment the usable
        # token exists anywhere; it goes straight into the mail and is dropped.
        link = f"{self._web_origin}/?reset_token={quote(token, safe='')}"
        hours = self._token_lifetime_minutes / 60
        validity = (
            f"{self._token_lifetime_minutes} dakika"
            if self._token_lifetime_minutes < 60
            else f"{hours:g} saat"
        )
        self._mailer.send(
            recipient=user.email,
            subject="Accountant şifre sıfırlama",
            message=MailMessage(
                greeting=f"Merhaba {user.display_name},",
                paragraphs=(
                    "Hesabının şifresini sıfırlamak için bir istek aldık. "
                    f"Aşağıdaki bağlantı {validity} geçerli ve yalnızca bir kez "
                    "kullanılabilir.",
                ),
                action=MailAction(label="Şifremi sıfırla", url=link),
                footnote=(
                    "Bu isteği sen yapmadıysan yapman gereken bir şey yok; "
                    "şifren değişmedi."
                ),
            ),
        )
        return True
