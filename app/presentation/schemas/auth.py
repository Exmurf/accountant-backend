from datetime import datetime, time
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.domain.identity.user import User


class RegisterRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    display_name: str
    daily_summary_enabled: bool
    daily_summary_time: time
    budget_alerts_enabled: bool
    roles: list[str]
    permissions: list[str]
    created_at: datetime

    @classmethod
    def from_domain(cls, user: User) -> "UserResponse":
        return cls(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            daily_summary_enabled=user.daily_summary_enabled,
            daily_summary_time=user.daily_summary_time,
            budget_alerts_enabled=user.budget_alerts_enabled,
            roles=sorted(user.roles),
            permissions=sorted(user.permissions),
            created_at=user.created_at,
        )


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class UpdateUserSettingsRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=100)
    daily_summary_enabled: bool
    daily_summary_time: time
    budget_alerts_enabled: bool


class LogoutResponse(BaseModel):
    success: bool = True
