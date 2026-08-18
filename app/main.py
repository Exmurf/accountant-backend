from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.presentation.http.router import api_router


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="Accountant API",
        description="Accountant gelir ve gider yönetimi API sözleşmesi",
        version="0.4.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router, prefix="/api/v1")

    return application


app = create_app()
