from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.application.identity.errors import (
    EmailAlreadyRegisteredError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
)
from app.application.identity.issue_session import IssueSession
from app.application.identity.login_user import LoginUser
from app.application.identity.refresh_session import RefreshSession
from app.application.identity.register_user import RegisterUser
from app.application.identity.revoke_session import RevokeSession
from app.core.config import get_settings
from app.domain.identity.user import User
from app.infrastructure.database.repositories.refresh_tokens import (
    SqlAlchemyRefreshTokenRepository,
)
from app.infrastructure.database.repositories.users import SqlAlchemyUserRepository
from app.infrastructure.database.session import get_database_session
from app.infrastructure.security.passwords import Argon2PasswordHasher
from app.infrastructure.security.tokens import JwtTokenService, OpaqueRefreshTokenService
from app.presentation.dependencies.auth import (
    ACCESS_COOKIE_NAME,
    get_current_user,
)
from app.presentation.schemas.auth import (
    LoginRequest,
    LogoutResponse,
    RegisterRequest,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["authentication"])
REFRESH_COOKIE_NAME = "accountant_refresh"


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
    response: Response,
    session: Annotated[Session, Depends(get_database_session)],
) -> UserResponse:
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
    response: Response,
    session: Annotated[Session, Depends(get_database_session)],
) -> UserResponse:
    use_case = LoginUser(
        SqlAlchemyUserRepository(session),
        Argon2PasswordHasher(),
    )
    try:
        user = use_case.execute(str(payload.email), payload.password)
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-posta veya şifre hatalı.",
        ) from None
    except InactiveUserError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kullanıcı hesabı devre dışı.",
        ) from None

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


@router.get("/me", response_model=UserResponse)
def me(user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return UserResponse.from_domain(user)


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
