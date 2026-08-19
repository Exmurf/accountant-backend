from fastapi import APIRouter

from app.presentation.http.auth import router as auth_router
from app.presentation.http.ledger import router as ledger_router
from app.presentation.http.savings import router as savings_router
from app.presentation.http.system import router as system_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(ledger_router)
api_router.include_router(savings_router)
api_router.include_router(system_router)
