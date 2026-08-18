from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.application.identity.errors import EmailAlreadyRegisteredError
from app.domain.identity.user import User
from app.infrastructure.database.models.identity import RoleModel, UserModel


class SqlAlchemyUserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_email(self, email: str) -> User | None:
        model = self._session.scalar(self._user_query().where(UserModel.email == email))
        return self._to_domain(model) if model is not None else None

    def get_by_id(self, user_id: UUID) -> User | None:
        model = self._session.scalar(self._user_query().where(UserModel.id == user_id))
        return self._to_domain(model) if model is not None else None

    def add(self, email: str, display_name: str, password_hash: str) -> User:
        user_role = self._session.scalar(
            select(RoleModel).where(RoleModel.name == "USER")
        )
        if user_role is None:
            raise RuntimeError("USER role has not been seeded")

        model = UserModel(
            email=email,
            display_name=display_name,
            password_hash=password_hash,
            roles=[user_role],
        )
        self._session.add(model)

        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            raise EmailAlreadyRegisteredError from error

        persisted = self._session.scalar(
            self._user_query().where(UserModel.id == model.id)
        )
        if persisted is None:
            raise RuntimeError("Created user could not be loaded")
        return self._to_domain(persisted)

    @staticmethod
    def _user_query():  # type: ignore[no-untyped-def]
        return select(UserModel).options(
            selectinload(UserModel.roles).selectinload(RoleModel.permissions)
        )

    @staticmethod
    def _to_domain(model: UserModel) -> User:
        permissions = {
            permission.code for role in model.roles for permission in role.permissions
        }
        return User(
            id=model.id,
            email=model.email,
            display_name=model.display_name,
            password_hash=model.password_hash,
            is_active=model.is_active,
            roles=frozenset(role.name for role in model.roles),
            permissions=frozenset(permissions),
            created_at=model.created_at,
        )
