from fastapi import APIRouter

from app.api.endpoints.health import router as health_router

main_router = APIRouter(prefix="/api/v1")
main_router.include_router(health_router)
