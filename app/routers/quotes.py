"""Rotas do cliente: escolher tipo de cotacao, solicitar, preencher a
Solicitacao de Frete (apos aprovacao pelo comercial) e acompanhar pelas
cotacoes do e-mail. A decisao (aprovar/reprovar) e sempre do time comercial,
lancada no painel."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import crud, emails
from app.constants import (
    OPCAO_CARROCERIA,
    OPCAO_TIPO_VEICULO,
    PAGADOR_OPCOES,
    STATUS_APROVADA,
    STATUS_ENVIADA_LOGISTICA,
    STATUS_FRETE_SOLICITADO,
    STATUS_NEGOCIACAO,
    STATUS_OC_EMITIDA,
    STATUS_REPROVADA,
    STATUS_RESPONDIDA,
    TIPO_COTACAO_COMPLETA,
    TIPOS_MATERIAL,
)
from app.database import get_db
from app.forms import (
    QuoteForm,
    SolicitacaoFreteForm,
    prefill_from_quote,
    prefill_from_quote_for_solicitacao,
)
from app.security import (
    client_can_view,
    get_csrf_token,
    grant_client_access,
    validate_csrf,
)
from app.templating import render
from app.utils import utcnow

router = APIRouter()

STATUS_RESPONDIDA_OU_DEPOIS = (
    STATUS_RESPONDIDA,
    STATUS_NEGOCIACAO,
    STATUS_APROVADA,
    STATUS_REPROVADA,
    STATUS_FRETE_SOLICITADO,
    STATUS_OC_EMITIDA,
    STATUS_ENVIADA_LOGISTICA,
)


def _form_context(
    request: Request,
    values: dict,
    errors: dict | None = None,
    *,
    tipo_cotacao: str = TIPO_COTACAO_COMPLETA,
    carrocerias: list[str] | None = None,
    tipos_veiculo: list[str] | None = None,
):
    return {
        "tipo_cotacao": tipo_cotacao,
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
def choose_quote_type(request: Request, base: str | None = None, db: Session = Depends(get_db)):
    # "Cotação Rápida" foi descontinuada -- so existe mais um tipo de
    # cotacao, entao a tela de escolha vira redirect direto pro formulario.
    destino = "/cotacao/nova?tipo=completa"
    if base:
        destino += f"&base={base}"
    return RedirectResponse(destino, status_code=303)


@router.get("/cotacao/nova")
def new_quote(
    request: Request,
    tipo: str = TIPO_COTACAO_COMPLETA,
    base: str | None = None,
    db: Session = Depends(get_db),
):
    tipo_cotacao = TIPO_COTACAO_COMPLETA  # unico tipo oferecido
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
        **_form_context(
            request, values, tipo_cotacao=tipo_cotacao,
            carrocerias=carrocerias, tipos_veiculo=tipos_veiculo,
        ),
    )


@router.post("/cotacao/nova")
async def submit_quote(request: Request, db: Session = Depends(get_db)):
    form = dict((await request.form()))
    tipo_cotacao = TIPO_COTACAO_COMPLETA  # unico tipo oferecido
    carrocerias = crud.opcao_names(db, OPCAO_CARROCERIA)
    tipos_veiculo = crud.opcao_names(db, OPCAO_TIPO_VEICULO)

    if not validate_csrf(request, form.get("csrf_token")):
        return render(
            request,
            "cotacao_form.html",
            base_code=None,
            **_form_context(
                request, form, {"__all__": "Sessão expirada. Envie novamente."},
                tipo_cotacao=tipo_cotacao, carrocerias=carrocerias, tipos_veiculo=tipos_veiculo,
            ),
        )

    qf = QuoteForm(
        form, tipo_cotacao=tipo_cotacao,
        allowed_carrocerias=carrocerias, allowed_tipos_veiculo=tipos_veiculo,
    )
    if not qf.validate():
        return render(
            request,
            "cotacao_form.html",
            base_code=form.get("base_code") or None,
            **_form_context(
                request, {**form}, qf.errors,  # devolve o que o cliente digitou
                tipo_cotacao=tipo_cotacao, carrocerias=carrocerias, tipos_veiculo=tipos_veiculo,
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
            error="Informe um e-mail válido.",
            email=email,
        )

    quotes = crud.list_quotes_by_email(db, email)
    if not quotes:
        return render(
            request,
            "acompanhar.html",
            csrf_token=get_csrf_token(request),
            error="Não encontramos cotações para esse e-mail.",
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


def _quote_detail_context(request: Request, quote) -> dict:
    return dict(
        quote=quote,
        proposal=quote.proposal,
        respondida=quote.status in STATUS_RESPONDIDA_OU_DEPOIS,
        csrf_token=get_csrf_token(request),
        t=request.query_params.get("t", ""),
    )


@router.get("/cotacao/{code}")
def quote_detail(request: Request, code: str, t: str | None = None, db: Session = Depends(get_db)):
    quote = crud.get_quote_by_code(db, code)
    if not quote:
        return render(request, "nao_encontrada.html", code=code)
    if not client_can_view(request, code, t):
        return RedirectResponse("/acompanhar", status_code=303)

    grant_client_access(request, code)
    return render(request, "proposta.html", **_quote_detail_context(request, quote))




@router.get("/cotacao/{code}/solicitacao")
def solicitacao_form(request: Request, code: str, t: str | None = None, db: Session = Depends(get_db)):
    quote = crud.get_quote_by_code(db, code)
    if not quote:
        return render(request, "nao_encontrada.html", code=code)
    if not client_can_view(request, code, t):
        return RedirectResponse("/acompanhar", status_code=303)
    if quote.status not in (STATUS_APROVADA, STATUS_FRETE_SOLICITADO):
        return RedirectResponse(f"/cotacao/{code}", status_code=303)

    grant_client_access(request, code)
    values = {}
    if quote.solicitacao:
        s = quote.solicitacao
        values = {
            "pagador": s.pagador, "pagador_documento": s.pagador_documento,
            "fornecedor_nome": s.fornecedor_nome, "fornecedor_contato": s.fornecedor_contato,
            "destinatario_nome": s.destinatario_nome, "destinatario_contato": s.destinatario_contato,
            "valor_nf": s.valor_nf, "observacoes_operacionais": s.observacoes_operacionais,
        }
    else:
        values = prefill_from_quote_for_solicitacao(quote)
    return render(
        request, "solicitacao_frete.html",
        quote=quote, values=values, errors={}, pagador_opcoes=PAGADOR_OPCOES,
        csrf_token=get_csrf_token(request), t=t or "",
    )


@router.post("/cotacao/{code}/solicitacao")
async def solicitacao_submit(request: Request, code: str, db: Session = Depends(get_db)):
    form = dict((await request.form()))
    quote = crud.get_quote_by_code(db, code)
    if not quote or not client_can_view(request, code, form.get("t")):
        return RedirectResponse("/acompanhar", status_code=303)
    if quote.status not in (STATUS_APROVADA, STATUS_FRETE_SOLICITADO):
        return RedirectResponse(f"/cotacao/{code}", status_code=303)
    if not validate_csrf(request, form.get("csrf_token")):
        return RedirectResponse(f"/cotacao/{code}/solicitacao", status_code=303)

    sf = SolicitacaoFreteForm(form)
    if not sf.validate():
        return render(
            request, "solicitacao_frete.html",
            quote=quote, values={**form}, errors=sf.errors, pagador_opcoes=PAGADOR_OPCOES,
            csrf_token=get_csrf_token(request), t=form.get("t", ""),
        )

    solicitacao = crud.create_or_update_solicitacao(db, quote, sf.values)
    emails.send_solicitacao_to_comercial(quote, solicitacao)
    return RedirectResponse(f"/cotacao/{code}", status_code=303)
