from fastapi import APIRouter

from app.api.endpoints.health import router as health_router
from app.api.endpoints.marts import router as marts_router

main_router = APIRouter(prefix="/api/v1")
main_router.include_router(health_router)
main_router.include_router(marts_router)
