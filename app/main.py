import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.presentation.http.response_envelope import ApiResponseEnvelopeMiddleware
from app.presentation.http.router import api_router
from app.infrastructure.ledger.runtime import subscription_scheduler
from app.infrastructure.notifications.runtime import (
    notification_scheduler,
    stop_scheduler,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    scheduler_tasks: list[asyncio.Task[None]] = [
        asyncio.create_task(subscription_scheduler())
    ]
    if settings.mail_enabled:
        scheduler_tasks.append(asyncio.create_task(notification_scheduler()))
    yield
    for task in scheduler_tasks:
        await stop_scheduler(task)


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="Accountant API",
        description="Accountant gelir ve gider yönetimi API sözleşmesi",
        version="0.6.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(ApiResponseEnvelopeMiddleware)
    application.include_router(api_router, prefix="/api/v1")

    return application


app = create_app()
