from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Cookie,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.application.identity.errors import (
    EmailAlreadyRegisteredError,
    EmailUnchangedError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidEmailChangeTokenError,
    InvalidPasswordResetTokenError,
    InvalidRefreshTokenError,
    PasswordUnchangedError,
    UnreachableEmailError,
)
from app.application.identity.change_email import (
    ConfirmEmailChange,
    RequestEmailChange,
)
from app.application.identity.change_password import ChangePassword
from app.application.identity.issue_session import IssueSession
from app.application.identity.login_user import LoginUser
from app.application.identity.refresh_session import RefreshSession
from app.application.identity.register_user import RegisterUser
from app.application.identity.reset_password import ResetPassword
from app.application.identity.revoke_session import RevokeSession
from app.application.identity.update_settings import UpdateUserSettings
from app.application.security.ports import RateLimiter
from app.core.config import get_settings
from app.domain.identity.user import User
from app.infrastructure.database.repositories.email_changes import (
    SqlAlchemyEmailChangeTokenRepository,
)
from app.infrastructure.database.repositories.password_resets import (
    SqlAlchemyPasswordResetTokenRepository,
)
from app.infrastructure.database.repositories.refresh_tokens import (
    SqlAlchemyRefreshTokenRepository,
)
from app.infrastructure.database.repositories.users import SqlAlchemyUserRepository
from app.infrastructure.database.session import get_database_session
from app.infrastructure.security.passwords import Argon2PasswordHasher
from app.infrastructure.identity.runtime import (
    deliver_email_change_notice,
    deliver_email_change_warning,
    deliver_password_reset,
)
from app.infrastructure.mail.smtp import SmtpMailSender
from app.infrastructure.security.tokens import (
    EmailChangeTokenService,
    JwtTokenService,
    OpaqueRefreshTokenService,
    PasswordResetTokenService,
)
from app.presentation.dependencies.auth import (
    ACCESS_COOKIE_NAME,
    get_current_user,
)
from app.presentation.dependencies.rate_limit import (
    client_address,
    enforce,
    get_rate_limiter,
)
from app.presentation.schemas.auth import (
    ChangeEmailRequest,
    ChangePasswordRequest,
    ConfirmEmailChangeRequest,
    EmailChangeRequestedResponse,
    ForgotPasswordRequest,
    LoginRequest,
    LogoutResponse,
    PasswordResetCompletedResponse,
    PasswordResetRequestedResponse,
    RegisterRequest,
    ResetPasswordRequest,
    UpdateUserSettingsRequest,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["authentication"])
REFRESH_COOKIE_NAME = "accountant_refresh"
TOO_MANY_LOGINS = "Çok fazla başarısız giriş denemesi."
TOO_MANY_REGISTRATIONS = "Çok fazla kayıt denemesi."
TOO_MANY_PASSWORD_ATTEMPTS = "Çok fazla başarısız şifre denemesi."
TOO_MANY_RESET_REQUESTS = "Çok fazla şifre sıfırlama isteği."
TOO_MANY_EMAIL_CHANGES = "Çok fazla e-posta değiştirme isteği."


def issue_session(response: Response, user: User, session: Session) -> None:
    settings = get_settings()
    tokens = IssueSession(
        access_tokens=JwtTokenService(settings),
        refresh_tokens=OpaqueRefreshTokenService(),
        refresh_token_repository=SqlAlchemyRefreshTokenRepository(session),
        refresh_token_days=settings.refresh_token_days,
    ).execute(user)
    set_session_cookies(response, tokens.access_token, tokens.refresh_token)


def set_session_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
) -> None:
    settings = get_settings()
    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=access_token,
        max_age=settings.access_token_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=settings.refresh_token_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/api/v1/auth",
    )


def clear_session_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE_NAME, path="/")
    response.delete_cookie(REFRESH_COOKIE_NAME, path="/api/v1/auth")


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_database_session)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> UserResponse:
    settings = get_settings()
    if settings.rate_limit_enabled:
        address_key = f"register:ip:{client_address(request)}"
        enforce(
            limiter.peek(
                address_key,
                settings.register_max_attempts,
                settings.register_window_seconds,
            ),
            TOO_MANY_REGISTRATIONS,
        )
        limiter.record(address_key, settings.register_window_seconds)

    use_case = RegisterUser(
        SqlAlchemyUserRepository(session),
        Argon2PasswordHasher(),
    )
    try:
        user = use_case.execute(
            email=str(payload.email),
            display_name=payload.display_name,
            password=payload.password,
        )
    except EmailAlreadyRegisteredError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu e-posta adresi zaten kayıtlı.",
        ) from None

    issue_session(response, user, session)
    return UserResponse.from_domain(user)


@router.post("/login", response_model=UserResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_database_session)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> UserResponse:
    settings = get_settings()
    # Normalised exactly as the use case does it, so an account cannot be
    # handed a fresh budget by varying the capitalisation of its address.
    email = str(payload.email).strip().lower()
    email_key = f"login:email:{email}"
    address_key = f"login:ip:{client_address(request)}"

    if settings.rate_limit_enabled:
        enforce(
            limiter.peek(
                address_key,
                settings.login_ip_max_attempts,
                settings.login_window_seconds,
            ),
            TOO_MANY_LOGINS,
        )
        enforce(
            limiter.peek(
                email_key,
                settings.login_max_attempts,
                settings.login_window_seconds,
            ),
            TOO_MANY_LOGINS,
        )

    use_case = LoginUser(
        SqlAlchemyUserRepository(session),
        Argon2PasswordHasher(),
    )
    try:
        user = use_case.execute(email, payload.password)
    except InvalidCredentialsError:
        # An unknown address and a wrong password raise the same error, so
        # the counter cannot be read as an answer to whether an account exists.
        if settings.rate_limit_enabled:
            limiter.record(address_key, settings.login_window_seconds)
            limiter.record(email_key, settings.login_window_seconds)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-posta veya şifre hatalı.",
        ) from None
    except InactiveUserError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kullanıcı hesabı devre dışı.",
        ) from None

    if settings.rate_limit_enabled:
        # The right password clears the account's budget but not the caller's:
        # signing in to your own account must not wipe a scan of other
        # accounts run from the same address.
        limiter.reset(email_key)

    issue_session(response, user, session)
    return UserResponse.from_domain(user)


@router.post("/refresh", response_model=LogoutResponse)
def refresh(
    response: Response,
    session: Annotated[Session, Depends(get_database_session)],
    refresh_token: Annotated[
        str | None,
        Cookie(alias=REFRESH_COOKIE_NAME),
    ] = None,
) -> LogoutResponse | Response:
    if refresh_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Oturum yenilenemedi.",
        )

    settings = get_settings()
    try:
        tokens = RefreshSession(
            users=SqlAlchemyUserRepository(session),
            access_tokens=JwtTokenService(settings),
            refresh_tokens=OpaqueRefreshTokenService(),
            refresh_token_repository=SqlAlchemyRefreshTokenRepository(session),
            refresh_token_days=settings.refresh_token_days,
        ).execute(refresh_token)
    except (InvalidRefreshTokenError, InactiveUserError):
        unauthorized_response = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Oturum yenilenemedi. Lütfen tekrar giriş yapın."},
        )
        clear_session_cookies(unauthorized_response)
        return unauthorized_response

    set_session_cookies(response, tokens.access_token, tokens.refresh_token)
    return LogoutResponse()


@router.post(
    "/password/forgot",
    response_model=PasswordResetRequestedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> PasswordResetRequestedResponse:
    settings = get_settings()
    email = str(payload.email).strip().lower()
    if settings.rate_limit_enabled:
        address_key = f"reset-request:ip:{client_address(request)}"
        email_key = f"reset-request:email:{email}"
        enforce(
            limiter.peek(
                address_key,
                settings.password_reset_ip_max_attempts,
                settings.password_reset_window_seconds,
            ),
            TOO_MANY_RESET_REQUESTS,
        )
        enforce(
            limiter.peek(
                email_key,
                settings.password_reset_max_attempts,
                settings.password_reset_window_seconds,
            ),
            TOO_MANY_RESET_REQUESTS,
        )
        limiter.record(address_key, settings.password_reset_window_seconds)
        limiter.record(email_key, settings.password_reset_window_seconds)

    # Every part of the work runs after the response, so a registered
    # address and an unknown one are indistinguishable, in what comes back
    # and in how long it took.
    background_tasks.add_task(deliver_password_reset, email)
    return PasswordResetRequestedResponse()


@router.post("/password/reset", response_model=PasswordResetCompletedResponse)
def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    session: Annotated[Session, Depends(get_database_session)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> PasswordResetCompletedResponse:
    settings = get_settings()
    address_key = f"reset-submit:ip:{client_address(request)}"
    if settings.rate_limit_enabled:
        enforce(
            limiter.peek(
                address_key,
                settings.login_ip_max_attempts,
                settings.login_window_seconds,
            ),
            TOO_MANY_RESET_REQUESTS,
        )

    try:
        ResetPassword(
            users=SqlAlchemyUserRepository(session),
            passwords=Argon2PasswordHasher(),
            reset_tokens=SqlAlchemyPasswordResetTokenRepository(session),
            token_service=PasswordResetTokenService(),
            refresh_token_repository=SqlAlchemyRefreshTokenRepository(session),
        ).execute(token=payload.token, new_password=payload.new_password)
    except InvalidPasswordResetTokenError:
        if settings.rate_limit_enabled:
            limiter.record(address_key, settings.login_window_seconds)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Bağlantı geçersiz ya da süresi dolmuş. "
                "Lütfen yeniden şifre sıfırlama isteği gönder."
            ),
        ) from None

    # No session is opened here on purpose: whoever follows the link proves
    # they hold the mailbox, not that they are sitting at a trusted device.
    return PasswordResetCompletedResponse()


@router.get("/me", response_model=UserResponse)
def me(user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return UserResponse.from_domain(user)


@router.patch("/me", response_model=UserResponse)
def update_me(
    payload: UpdateUserSettingsRequest,
    session: Annotated[Session, Depends(get_database_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    updated_user = UpdateUserSettings(
        SqlAlchemyUserRepository(session)
    ).execute(
        user_id=user.id,
        display_name=payload.display_name,
        daily_summary_enabled=payload.daily_summary_enabled,
        daily_summary_time=payload.daily_summary_time,
        budget_alerts_enabled=payload.budget_alerts_enabled,
    )
    return UserResponse.from_domain(updated_user)


@router.patch("/me/password", response_model=UserResponse)
def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    session: Annotated[Session, Depends(get_database_session)],
    user: Annotated[User, Depends(get_current_user)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> UserResponse:
    # This endpoint takes the current password too, so it is one more place
    # a password can be guessed. It is keyed by user rather than by address
    # because reaching it already requires a session.
    settings = get_settings()
    password_key = f"password:user:{user.id}"
    if settings.rate_limit_enabled:
        enforce(
            limiter.peek(
                password_key,
                settings.login_max_attempts,
                settings.login_window_seconds,
            ),
            TOO_MANY_PASSWORD_ATTEMPTS,
        )

    try:
        updated_user = ChangePassword(
            users=SqlAlchemyUserRepository(session),
            passwords=Argon2PasswordHasher(),
            refresh_token_repository=SqlAlchemyRefreshTokenRepository(session),
        ).execute(
            user_id=user.id,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except InvalidCredentialsError:
        if settings.rate_limit_enabled:
            limiter.record(password_key, settings.login_window_seconds)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Mevcut şifren hatalı.",
        ) from None
    except PasswordUnchangedError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Yeni şifren mevcut şifrenden farklı olmalı.",
        ) from None

    if settings.rate_limit_enabled:
        limiter.reset(password_key)

    # Every refresh token was just revoked, so this session needs a fresh one.
    issue_session(response, updated_user, session)
    return UserResponse.from_domain(updated_user)


@router.post(
    "/email/change",
    response_model=EmailChangeRequestedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def change_email(
    payload: ChangeEmailRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Annotated[Session, Depends(get_database_session)],
    user: Annotated[User, Depends(get_current_user)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> EmailChangeRequestedResponse:
    settings = get_settings()
    if not settings.mail_enabled:
        # The whole flow turns on a link arriving somewhere, so there is nothing
        # useful to do here without a configured sender.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="E-posta gönderimi yapılandırılmadığı için adres değiştirilemiyor.",
        )

    user_key = f"email-change:user:{user.id}"
    address_key = f"email-change:ip:{client_address(request)}"
    if settings.rate_limit_enabled:
        for key in (address_key, user_key):
            enforce(
                limiter.peek(
                    key,
                    settings.email_change_max_attempts,
                    settings.email_change_window_seconds,
                ),
                TOO_MANY_EMAIL_CHANGES,
            )

    use_case = RequestEmailChange(
        users=SqlAlchemyUserRepository(session),
        passwords=Argon2PasswordHasher(),
        change_tokens=SqlAlchemyEmailChangeTokenRepository(session),
        token_service=EmailChangeTokenService(),
        mailer=SmtpMailSender(settings),
        web_origin=settings.web_origin,
        token_lifetime_minutes=settings.email_change_token_minutes,
    )
    try:
        new_email = use_case.execute(
            user=user,
            new_email=str(payload.new_email),
            current_password=payload.current_password,
        )
    except InvalidCredentialsError:
        if settings.rate_limit_enabled:
            limiter.record(address_key, settings.email_change_window_seconds)
            limiter.record(user_key, settings.email_change_window_seconds)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Mevcut şifren hatalı.",
        ) from None
    except EmailUnchangedError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Bu zaten mevcut e-posta adresin.",
        ) from None
    except UnreachableEmailError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Bu alan adına e-posta gönderilemiyor.",
        ) from None
    except EmailAlreadyRegisteredError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu e-posta adresi zaten kayıtlı.",
        ) from None

    if settings.rate_limit_enabled:
        limiter.record(address_key, settings.email_change_window_seconds)
        limiter.record(user_key, settings.email_change_window_seconds)

    # A courtesy to whoever holds the old mailbox, and not worth failing the
    # request over: the confirmation link has already been sent.
    background_tasks.add_task(deliver_email_change_warning, user, new_email)
    return EmailChangeRequestedResponse()


@router.post("/email/confirm", response_model=UserResponse)
def confirm_email_change(
    payload: ConfirmEmailChangeRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Annotated[Session, Depends(get_database_session)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> UserResponse:
    # No session is required: the link is opened wherever the new mailbox
    # is read, which is rarely the browser that asked for the change.
    settings = get_settings()
    address_key = f"email-confirm:ip:{client_address(request)}"
    if settings.rate_limit_enabled:
        enforce(
            limiter.peek(
                address_key,
                settings.login_ip_max_attempts,
                settings.login_window_seconds,
            ),
            TOO_MANY_EMAIL_CHANGES,
        )

    try:
        updated_user, previous_email = ConfirmEmailChange(
            users=SqlAlchemyUserRepository(session),
            change_tokens=SqlAlchemyEmailChangeTokenRepository(session),
            token_service=EmailChangeTokenService(),
        ).execute(payload.token)
    except InvalidEmailChangeTokenError:
        if settings.rate_limit_enabled:
            limiter.record(address_key, settings.login_window_seconds)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Bağlantı geçersiz ya da süresi dolmuş. "
                "Lütfen ayarlardan yeniden istek gönder."
            ),
        ) from None
    except EmailAlreadyRegisteredError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Bu e-posta adresi sen onaylamadan önce başka bir hesaba "
                "kaydedildi."
            ),
        ) from None

    background_tasks.add_task(
        deliver_email_change_notice,
        updated_user,
        previous_email,
    )
    return UserResponse.from_domain(updated_user)


@router.post("/logout", response_model=LogoutResponse)
def logout(
    response: Response,
    session: Annotated[Session, Depends(get_database_session)],
    refresh_token: Annotated[
        str | None,
        Cookie(alias=REFRESH_COOKIE_NAME),
    ] = None,
) -> LogoutResponse:
    if refresh_token is not None:
        RevokeSession(
            refresh_tokens=OpaqueRefreshTokenService(),
            refresh_token_repository=SqlAlchemyRefreshTokenRepository(session),
        ).execute(refresh_token)
    clear_session_cookies(response)
    return LogoutResponse()
