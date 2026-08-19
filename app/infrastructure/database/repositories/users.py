from datetime import UTC, datetime, time
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

    def list_active(self) -> list[User]:
        models = self._session.scalars(
            self._user_query()
            .where(UserModel.is_active.is_(True))
            .order_by(UserModel.email)
        ).all()
        return [self._to_domain(model) for model in models]

    def list_all(self) -> list[User]:
        models = self._session.scalars(
            self._user_query().order_by(UserModel.created_at.desc())
        ).all()
        return [self._to_domain(model) for model in models]

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

    def update_settings(
        self,
        user_id: UUID,
        display_name: str,
        daily_summary_enabled: bool,
        daily_summary_time: time,
        budget_alerts_enabled: bool,
    ) -> User | None:
        model = self._session.get(UserModel, user_id)
        if model is None:
            return None

        model.display_name = display_name
        model.daily_summary_enabled = daily_summary_enabled
        model.daily_summary_time = daily_summary_time
        model.budget_alerts_enabled = budget_alerts_enabled
        self._session.commit()

        persisted = self._session.scalar(
            self._user_query().where(UserModel.id == user_id)
        )
        if persisted is None:
            return None
        return self._to_domain(persisted)

    def update_password(self, user_id: UUID, password_hash: str) -> User | None:
        model = self._session.get(UserModel, user_id)
        if model is None:
            return None

        model.password_hash = password_hash
        # Access tokens carry whole-second `iat` values, so the marker is kept at
        # the same resolution; a token minted in this second stays valid.
        model.password_changed_at = datetime.now(UTC).replace(microsecond=0)
        self._session.commit()

        persisted = self._session.scalar(
            self._user_query().where(UserModel.id == user_id)
        )
        if persisted is None:
            return None
        return self._to_domain(persisted)

    def set_savings_goal(self, user_id: UUID, amount_minor: int) -> int | None:
        model = self._session.get(UserModel, user_id)
        if model is None:
            return None

        model.savings_goal_minor = amount_minor
        self._session.commit()
        return model.savings_goal_minor

    def set_opening_balance(self, user_id: UUID, amount_minor: int) -> int | None:
        model = self._session.get(UserModel, user_id)
        if model is None:
            return None

        model.opening_balance_minor = amount_minor
        self._session.commit()
        return model.opening_balance_minor

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
            opening_balance_minor=model.opening_balance_minor,
            savings_goal_minor=model.savings_goal_minor,
            daily_summary_enabled=model.daily_summary_enabled,
            daily_summary_time=model.daily_summary_time,
            budget_alerts_enabled=model.budget_alerts_enabled,
            roles=frozenset(role.name for role in model.roles),
            permissions=frozenset(permissions),
            created_at=model.created_at,
            password_changed_at=model.password_changed_at,
        )
