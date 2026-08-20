from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from app.application.identity.errors import (
    EmailAlreadyRegisteredError,
    EmailUnchangedError,
    InvalidCredentialsError,
    InvalidEmailChangeTokenError,
    UnreachableEmailError,
)
from app.application.identity.ports import (
    EmailChangeTokenRepository,
    PasswordHasher,
    RefreshTokenService,
    UserRepository,
)
from app.application.notifications.ports import MailSender
from app.domain.identity.user import User

PLACEHOLDER_DOMAINS = frozenset({"example.com", "example.org", "example.net"})


def _is_unreachable(email: str) -> bool:
    return email.rsplit("@", 1)[-1].lower() in PLACEHOLDER_DOMAINS


class RequestEmailChange:
    """Mail a confirmation link to the address somebody wants to move to.

    The link goes to the new address because holding that mailbox is the only
    thing that proves it is theirs, and the old address is told separately so
    the real owner sees the attempt even if they did not make it.
    """

    def __init__(
        self,
        users: UserRepository,
        passwords: PasswordHasher,
        change_tokens: EmailChangeTokenRepository,
        token_service: RefreshTokenService,
        mailer: MailSender,
        web_origin: str,
        token_lifetime_minutes: int,
    ) -> None:
        self._users = users
        self._passwords = passwords
        self._change_tokens = change_tokens
        self._token_service = token_service
        self._mailer = mailer
        self._web_origin = web_origin.rstrip("/")
        self._token_lifetime_minutes = token_lifetime_minutes

    def execute(self, user: User, new_email: str, current_password: str) -> str:
        # A session cookie is not enough on its own. Mail is the recovery
        # channel, so letting a stolen session repoint it would turn a borrowed
        # session into a permanent takeover.
        if not self._passwords.verify(current_password, user.password_hash):
            raise InvalidCredentialsError

        normalized = new_email.strip().lower()
        if normalized == user.email:
            raise EmailUnchangedError
        if _is_unreachable(normalized):
            # No link can arrive there, so refusing now beats leaving somebody
            # waiting for a mail that was never going to be deliverable.
            raise UnreachableEmailError
        if self._users.get_by_email(normalized) is not None:
            raise EmailAlreadyRegisteredError

        now = datetime.now(UTC)
        token = self._token_service.create()
        self._change_tokens.replace_for_user(
            user_id=user.id,
            new_email=normalized,
            token_hash=self._token_service.hash(token),
            expires_at=now + timedelta(minutes=self._token_lifetime_minutes),
            now=now,
        )

        hours = self._token_lifetime_minutes / 60
        validity = (
            f"{self._token_lifetime_minutes} dakika"
            if self._token_lifetime_minutes < 60
            else f"{hours:g} saat"
        )
        link = f"{self._web_origin}/?email_token={quote(token, safe='')}"
        self._mailer.send(
            recipient=normalized,
            subject="Accountant e-posta adresi doğrulama",
            text_body=(
                f"Merhaba {user.display_name},\n\n"
                f"Accountant hesabının e-posta adresini {user.email} yerine bu "
                "adres olarak değiştirmek istedin. Onaylamak için aşağıdaki "
                f"bağlantıya tıkla. Bağlantı {validity} geçerli ve yalnızca bir "
                "kez kullanılabilir:\n\n"
                f"{link}\n\n"
                "Bu isteği sen yapmadıysan bu maili yok sayabilirsin; "
                "onaylanmadığı sürece hiçbir şey değişmez.\n\n"
                "Accountant"
            ),
        )
        return normalized

    def warn_previous_address(self, user: User, new_email: str) -> None:
        """Tell the address being left behind, without giving it the link.

        Its job is to let the rightful owner notice a change they did not ask
        for. A link here would hand an attacker who only has the old mailbox
        exactly what they lack.
        """
        self._mailer.send(
            recipient=user.email,
            subject="Accountant hesabının e-posta adresi değiştiriliyor",
            text_body=(
                f"Merhaba {user.display_name},\n\n"
                "Accountant hesabının e-posta adresinin "
                f"{new_email} olarak değiştirilmesi istendi. Değişiklik, yeni "
                "adrese gönderilen bağlantı onaylanana kadar geçerli olmaz.\n\n"
                "Bu isteği sen yapmadıysan şifreni hemen değiştir: isteği yapan "
                "kişi şifreni biliyor.\n\n"
                "Accountant"
            ),
        )


class ConfirmEmailChange:
    def __init__(
        self,
        users: UserRepository,
        change_tokens: EmailChangeTokenRepository,
        token_service: RefreshTokenService,
        mailer: MailSender,
    ) -> None:
        self._users = users
        self._change_tokens = change_tokens
        self._token_service = token_service
        self._mailer = mailer

    def execute(self, token: str) -> tuple[User, str]:
        now = datetime.now(UTC)
        pending = self._change_tokens.consume(self._token_service.hash(token), now)
        if pending is None:
            raise InvalidEmailChangeTokenError

        user = self._users.get_by_id(pending.user_id)
        if user is None or not user.is_active:
            raise InvalidEmailChangeTokenError

        previous_email = user.email
        # Checked again rather than trusted from the request: the address was
        # free when the link was mailed, and the mail may have sat unread while
        # somebody else registered it. The unique index is the last word.
        if self._users.get_by_email(pending.new_email) is not None:
            raise EmailAlreadyRegisteredError

        updated = self._users.update_email(pending.user_id, pending.new_email)
        if updated is None:
            raise RuntimeError("User behind a valid email token could not be updated")

        # Sessions survive: the password was proved when the change was asked
        # for, so there is nothing here to suggest the account is in the wrong
        # hands.
        self._notify_previous_address(updated, previous_email)
        return updated, previous_email

    def _notify_previous_address(self, user: User, previous_email: str) -> None:
        self._mailer.send(
            recipient=previous_email,
            subject="Accountant hesabının e-posta adresi değişti",
            text_body=(
                f"Merhaba {user.display_name},\n\n"
                "Accountant hesabının e-posta adresi "
                f"{user.email} olarak değiştirildi. Bundan sonra giriş ve şifre "
                "sıfırlama işlemleri yeni adres üzerinden yapılacak.\n\n"
                "Bu değişikliği sen yapmadıysan bize ulaş.\n\n"
                "Accountant"
            ),
        )
