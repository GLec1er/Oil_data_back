from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import main_router
from app.core.config import settings

app = FastAPI(title=settings.app_title)

# The API is read-only, so browsers only ever need GET from the static site.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["GET"],
    allow_headers=[],
)

app.include_router(main_router)
