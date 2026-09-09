"""Rotas do cliente: solicitar cotacao e acompanhar pelas cotacoes do e-mail."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import crud, emails
from app.constants import (
    OPCAO_CARROCERIA,
    OPCAO_TIPO_VEICULO,
    STATUS_APROVADA,
    STATUS_REPROVADA,
    STATUS_RESPONDIDA,
    TIPOS_MATERIAL,
)
from app.database import get_db
from app.forms import QuoteForm, prefill_from_quote
from app.security import (
    client_can_view,
    get_csrf_token,
    grant_client_access,
    validate_csrf,
)
from app.templating import render
from app.utils import utcnow

router = APIRouter()


def _form_context(
    request: Request,
    values: dict,
    errors: dict | None = None,
    *,
    carrocerias: list[str] | None = None,
    tipos_veiculo: list[str] | None = None,
):
    return {
        "tipos_material": TIPOS_MATERIAL,
        "tipos_veiculo": tipos_veiculo or [],
        "carrocerias": carrocerias or [],
        "values": values,
        "errors": errors or {},
        "today": utcnow().date().isoformat(),
        "csrf_token": get_csrf_token(request),
    }


@router.get("/")
def home(request: Request):
    return render(request, "home.html")


@router.get("/cotacao")
def new_quote(request: Request, base: str | None = None, db: Session = Depends(get_db)):
    values: dict = {}
    base_code = None
    if base:
        origem = crud.get_quote_by_code(db, base)
        if origem:
            values = prefill_from_quote(origem)
            base_code = origem.code
    carrocerias = crud.opcao_names(db, OPCAO_CARROCERIA)
    tipos_veiculo = crud.opcao_names(db, OPCAO_TIPO_VEICULO)
    return render(
        request,
        "cotacao_form.html",
        base_code=base_code,
        **_form_context(request, values, carrocerias=carrocerias, tipos_veiculo=tipos_veiculo),
    )


@router.post("/cotacao")
async def submit_quote(request: Request, db: Session = Depends(get_db)):
    form = dict((await request.form()))
    carrocerias = crud.opcao_names(db, OPCAO_CARROCERIA)
    tipos_veiculo = crud.opcao_names(db, OPCAO_TIPO_VEICULO)
    if not validate_csrf(request, form.get("csrf_token")):
        return render(
            request,
            "cotacao_form.html",
            base_code=None,
            **_form_context(
                request,
                form,
                {"__all__": "Sessao expirada. Envie novamente."},
                carrocerias=carrocerias,
                tipos_veiculo=tipos_veiculo,
            ),
        )

    qf = QuoteForm(form, allowed_carrocerias=carrocerias, allowed_tipos_veiculo=tipos_veiculo)
    if not qf.validate():
        return render(
            request,
            "cotacao_form.html",
            base_code=form.get("base_code") or None,
            **_form_context(
                request, {**form, **qf.values}, qf.errors,
                carrocerias=carrocerias, tipos_veiculo=tipos_veiculo,
            ),
        )

    quote = crud.create_quote(db, qf.values)
    emails.send_quote_to_comercial(quote)
    emails.send_confirmation_to_client(quote)
    grant_client_access(request, quote.code)
    return RedirectResponse(f"/cotacao/{quote.code}/enviada", status_code=303)


@router.get("/cotacao/{code}/enviada")
def quote_sent(request: Request, code: str, db: Session = Depends(get_db)):
    quote = crud.get_quote_by_code(db, code)
    if not quote:
        return RedirectResponse("/cotacao", status_code=303)
    return render(request, "confirmacao.html", quote=quote)


@router.get("/acompanhar")
def track_form(request: Request):
    return render(request, "acompanhar.html", csrf_token=get_csrf_token(request))


@router.post("/acompanhar")
async def track_lookup(request: Request, db: Session = Depends(get_db)):
    form = dict((await request.form()))
    email = (form.get("email") or "").strip().lower()

    if not email or "@" not in email:
        return render(
            request,
            "acompanhar.html",
            csrf_token=get_csrf_token(request),
            error="Informe um e-mail valido.",
            email=email,
        )

    quotes = crud.list_quotes_by_email(db, email)
    if not quotes:
        return render(
            request,
            "acompanhar.html",
            csrf_token=get_csrf_token(request),
            error="Nao encontramos cotacoes para esse e-mail.",
            email=email,
        )

    for q in quotes:
        grant_client_access(request, q.code)
    return RedirectResponse("/minhas-cotacoes", status_code=303)


@router.get("/minhas-cotacoes")
def my_quotes(request: Request, db: Session = Depends(get_db)):
    allowed = request.session.get("client_quotes", [])
    if not allowed:
        return RedirectResponse("/acompanhar", status_code=303)
    quotes = [q for c in allowed if (q := crud.get_quote_by_code(db, c))]
    quotes.sort(key=lambda q: q.created_at, reverse=True)
    return render(request, "minhas_cotacoes.html", quotes=quotes)


@router.get("/cotacao/{code}")
def quote_detail(
    request: Request,
    code: str,
    t: str | None = None,
    db: Session = Depends(get_db),
):
    quote = crud.get_quote_by_code(db, code)
    if not quote:
        return render(request, "nao_encontrada.html", code=code)
    if not client_can_view(request, code, t):
        return RedirectResponse("/acompanhar", status_code=303)

    grant_client_access(request, code)
    return render(
        request,
        "proposta.html",
        quote=quote,
        proposal=quote.proposal,
        respondida=quote.status
        in (STATUS_RESPONDIDA, STATUS_APROVADA, STATUS_REPROVADA),
    )
