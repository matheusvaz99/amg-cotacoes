"""Aplicacao FastAPI — site de Cotacao Rapida de Frete da AMG Logistica."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database import init_db
from app.routers import admin, quotes
from app.security import _RedirectException, redirect_exception_handler

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="AMG Logística — Cotação Rápida de Frete", lifespan=lifespan)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    https_only=not settings.is_dev,
    same_site="lax",
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.add_exception_handler(_RedirectException, redirect_exception_handler)

app.include_router(quotes.router)
app.include_router(admin.router)


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}
