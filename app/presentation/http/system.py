from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.application.system.get_health import GetSystemHealth

router = APIRouter(prefix="/health", tags=["system"])
get_system_health = GetSystemHealth()


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: Literal["accountant-api"]


@router.get("", response_model=HealthResponse, summary="API sağlık durumu")
def health() -> HealthResponse:
    return HealthResponse.model_validate(asdict(get_system_health.execute()))
