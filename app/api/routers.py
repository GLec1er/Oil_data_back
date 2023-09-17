from fastapi import APIRouter

#from app.api.endpoints import ()

main_router = APIRouter(prefix="/api/v1")
main_router.include_router()

