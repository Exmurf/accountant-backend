from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.identity.user import User
from app.infrastructure.database.repositories.users import SqlAlchemyUserRepository
from app.infrastructure.database.session import get_database_session
from app.infrastructure.security.tokens import JwtTokenService

ACCESS_COOKIE_NAME = "accountant_access"


def get_current_user(
    session: Annotated[Session, Depends(get_database_session)],
    token: Annotated[
        str | None,
        Cookie(alias=ACCESS_COOKIE_NAME),
    ] = None,
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Oturum açmanız gerekiyor.",
    )
    if token is None:
        raise unauthorized

    try:
        user_id = JwtTokenService(get_settings()).decode_subject(token)
    except (jwt.InvalidTokenError, ValueError, KeyError):
        raise unauthorized from None

    user = SqlAlchemyUserRepository(session).get_by_id(user_id)
    if user is None or not user.is_active:
        raise unauthorized
    return user


def require_permission(permission: str) -> Callable[..., User]:
    def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if permission not in user.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu işlem için yetkiniz yok.",
            )
        return user

    return dependency


def require_permissions(*permissions: str) -> Callable[..., User]:
    def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if not set(permissions).issubset(user.permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu işlem için yetkiniz yok.",
            )
        return user

    return dependency
