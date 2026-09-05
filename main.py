"""Entrypoint para `uvicorn main:app`. A aplicacao vive em app/main.py."""

from app.main import app

__all__ = ["app"]
