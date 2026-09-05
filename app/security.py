"""Sessao do admin, token de link do cliente e CSRF simples."""

from __future__ import annotations

import hmac
import secrets

from fastapi import Request
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import settings

_serializer = URLSafeTimedSerializer(settings.secret_key, salt="amg-client-link")

CLIENT_TOKEN_MAX_AGE = 60 * 60 * 24 * 60  # 60 dias


# ----- Token de acompanhamento do cliente -----------------------------------

def sign_quote_token(code: str) -> str:
    return _serializer.dumps(code.upper())


def verify_quote_token(token: str, code: str) -> bool:
    try:
        value = _serializer.loads(token, max_age=CLIENT_TOKEN_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return False
    return hmac.compare_digest(str(value).upper(), code.upper())


def client_can_view(request: Request, code: str, token: str | None) -> bool:
    """Cliente ve a cotacao via token do e-mail OU apos consulta em /acompanhar."""
    if token and verify_quote_token(token, code):
        return True
    allowed = request.session.get("client_quotes", [])
    return code.upper() in allowed


def grant_client_access(request: Request, code: str) -> None:
    allowed = set(request.session.get("client_quotes", []))
    allowed.add(code.upper())
    request.session["client_quotes"] = sorted(allowed)


# ----- Sessao do painel comercial ------------------------------------------

def admin_login(request: Request, username: str) -> None:
    request.session["admin_user"] = username


def admin_logout(request: Request) -> None:
    request.session.pop("admin_user", None)


def current_admin(request: Request) -> str | None:
    return request.session.get("admin_user")


def check_admin_credentials(username: str, password: str) -> bool:
    user_ok = hmac.compare_digest(username.strip(), settings.admin_user)
    pass_ok = hmac.compare_digest(password, settings.admin_pass)
    return user_ok and pass_ok


def require_admin(request: Request):
    """Dependencia: redireciona para /admin/login quando nao autenticado."""
    if not current_admin(request):
        nxt = request.url.path
        raise _RedirectException(f"/admin/login?next={nxt}")
    return current_admin(request)


class _RedirectException(Exception):
    def __init__(self, location: str):
        self.location = location


def redirect_exception_handler(request: Request, exc: _RedirectException):
    return RedirectResponse(exc.location, status_code=303)


# ----- CSRF ---------------------------------------------------------------

def get_csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token


def validate_csrf(request: Request, submitted: str | None) -> bool:
    expected = request.session.get("csrf_token")
    return bool(expected) and bool(submitted) and hmac.compare_digest(expected, submitted)
