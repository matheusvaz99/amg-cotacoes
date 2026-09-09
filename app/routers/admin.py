"""Painel comercial: login, fila de cotacoes e lancamento de propostas."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import crud, emails
from app.constants import (
    ADMIN_TABS,
    OPCOES_CATEGORIAS,
    STATUS_APROVADA,
    STATUS_REPROVADA,
    STATUS_RESPONDIDA,
)
from app.database import get_db
from app.forms import ProposalForm
from app.pdf import build_quote_pdf
from app.security import (
    admin_login,
    admin_logout,
    check_admin_credentials,
    current_admin,
    get_csrf_token,
    require_admin,
    validate_csrf,
)
from app.templating import render
from app.utils import calc_seguro, utcnow

router = APIRouter(prefix="/admin")


@router.get("/login")
def login_form(request: Request, next: str = "/admin"):
    if current_admin(request):
        return RedirectResponse(next, status_code=303)
    return render(
        request, "admin/login.html", next=next, csrf_token=get_csrf_token(request)
    )


@router.post("/login")
async def login_submit(request: Request):
    form = dict((await request.form()))
    nxt = form.get("next") or "/admin"
    if not validate_csrf(request, form.get("csrf_token")):
        return render(
            request,
            "admin/login.html",
            next=nxt,
            csrf_token=get_csrf_token(request),
            error="Sessao expirada. Tente novamente.",
        )
    username = (form.get("username") or "").strip()
    password = form.get("password") or ""
    if not check_admin_credentials(username, password):
        return render(
            request,
            "admin/login.html",
            next=nxt,
            csrf_token=get_csrf_token(request),
            error="Usuario ou senha invalidos.",
            username=username,
        )
    admin_login(request, username)
    return RedirectResponse(nxt, status_code=303)


@router.get("/logout")
def logout(request: Request):
    admin_logout(request)
    return RedirectResponse("/admin/login", status_code=303)


@router.get("")
def dashboard(
    request: Request,
    tab: str = "todas",
    q: str = "",
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if tab not in ADMIN_TABS:
        tab = "todas"
    quotes = crud.list_quotes(db, tab=tab, search=q)
    counts = {name: len(crud.list_quotes(db, tab=name)) for name in ADMIN_TABS}
    return render(
        request,
        "admin/lista.html",
        admin=admin,
        quotes=quotes,
        tab=tab,
        search=q,
        counts=counts,
    )


@router.get("/cotacao/{code}")
def quote_view(
    request: Request,
    code: str,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    quote = crud.get_quote_by_code(db, code)
    if not quote:
        return RedirectResponse("/admin", status_code=303)
    p = quote.proposal
    values = {
        "frete": p.frete if p else "",
        "pedagio": p.pedagio if p else "",
        "seguro": p.seguro if p else calc_seguro(quote.valor_nf),
        "custos_adicionais": p.custos_adicionais if p else "",
        "custos_adicionais_desc": p.custos_adicionais_desc if p else "",
        "prazo_entrega": p.prazo_entrega if p else "",
        "validade": p.validade.isoformat() if p else "",
        "observacoes": p.observacoes if p else "",
    }
    return render(
        request,
        "admin/responder.html",
        admin=admin,
        quote=quote,
        values=values,
        errors={},
        today=utcnow().date().isoformat(),
        csrf_token=get_csrf_token(request),
    )


@router.post("/cotacao/{code}")
async def quote_respond(
    request: Request,
    code: str,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    quote = crud.get_quote_by_code(db, code)
    if not quote:
        return RedirectResponse("/admin", status_code=303)

    form = dict((await request.form()))
    if not validate_csrf(request, form.get("csrf_token")):
        return RedirectResponse(f"/admin/cotacao/{code}", status_code=303)

    pf = ProposalForm(form, valor_nf=quote.valor_nf)
    if not pf.validate():
        return render(
            request,
            "admin/responder.html",
            admin=admin,
            quote=quote,
            values={**form, **pf.values},
            errors=pf.errors,
            today=utcnow().date().isoformat(),
            csrf_token=get_csrf_token(request),
        )

    proposal = crud.add_proposal(db, quote, pf.values, created_by=admin)
    emails.send_proposal_ready(quote, proposal)
    return RedirectResponse(f"/admin/cotacao/{code}?ok=1", status_code=303)


@router.post("/cotacao/{code}/aprovar")
async def quote_aprovar(
    request: Request,
    code: str,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    quote = crud.get_quote_by_code(db, code)
    if not quote:
        return RedirectResponse("/admin", status_code=303)
    form = dict((await request.form()))
    if not validate_csrf(request, form.get("csrf_token")):
        return RedirectResponse(f"/admin/cotacao/{code}", status_code=303)
    if quote.status in (STATUS_RESPONDIDA, STATUS_REPROVADA):
        crud.set_status(db, quote, STATUS_APROVADA, decision_note="")
        emails.send_decision_to_client(quote)
    return RedirectResponse(f"/admin/cotacao/{code}?ok=aprovada", status_code=303)


@router.post("/cotacao/{code}/reprovar")
async def quote_reprovar(
    request: Request,
    code: str,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    quote = crud.get_quote_by_code(db, code)
    if not quote:
        return RedirectResponse("/admin", status_code=303)
    form = dict((await request.form()))
    if not validate_csrf(request, form.get("csrf_token")):
        return RedirectResponse(f"/admin/cotacao/{code}", status_code=303)
    motivo = (form.get("motivo") or "").strip()
    if quote.status in (STATUS_RESPONDIDA, STATUS_APROVADA):
        crud.set_status(db, quote, STATUS_REPROVADA, decision_note=motivo)
        emails.send_decision_to_client(quote)
    return RedirectResponse(f"/admin/cotacao/{code}?ok=reprovada", status_code=303)


@router.get("/cotacao/{code}/pdf")
def quote_pdf(
    request: Request,
    code: str,
    inline: int = 0,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    quote = crud.get_quote_by_code(db, code)
    if not quote:
        return RedirectResponse("/admin", status_code=303)
    pdf_bytes = build_quote_pdf(quote)
    disposition = "inline" if inline else "attachment"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'{disposition}; filename="cotacao-{quote.code}.pdf"'
        },
    )


@router.post("/cotacao/{code}/enviar-pdf")
async def quote_send_pdf(
    request: Request,
    code: str,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    quote = crud.get_quote_by_code(db, code)
    if not quote:
        return RedirectResponse("/admin", status_code=303)
    form = dict((await request.form()))
    if not validate_csrf(request, form.get("csrf_token")):
        return RedirectResponse(f"/admin/cotacao/{code}", status_code=303)
    pdf_bytes = build_quote_pdf(quote)
    emails.send_quote_pdf_to_client(quote, pdf_bytes)
    return RedirectResponse(f"/admin/cotacao/{code}?ok=pdf", status_code=303)


# ----- Opcoes de cadastro (carrocerias, tipos de veiculo, ...) -----------
# Uma unica familia de rotas genericas, parametrizada por `categoria`,
# atende qualquer lista de opcoes do formulario de cotacao.

@router.get("/opcoes/{categoria}")
def opcoes_list(
    request: Request,
    categoria: str,
    ok: str = "",
    err: str = "",
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    info = OPCOES_CATEGORIAS.get(categoria)
    if not info:
        return RedirectResponse("/admin", status_code=303)
    return render(
        request,
        "admin/opcoes.html",
        admin=admin,
        categoria=categoria,
        info=info,
        opcoes=crud.list_opcoes(db, categoria),
        ok=ok,
        err=err,
        csrf_token=get_csrf_token(request),
    )


@router.post("/opcoes/{categoria}")
async def opcoes_add(
    request: Request,
    categoria: str,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if categoria not in OPCOES_CATEGORIAS:
        return RedirectResponse("/admin", status_code=303)
    form = dict((await request.form()))
    if not validate_csrf(request, form.get("csrf_token")):
        return RedirectResponse(f"/admin/opcoes/{categoria}", status_code=303)
    nome = (form.get("nome") or "").strip()
    if not nome:
        return RedirectResponse(f"/admin/opcoes/{categoria}?err=vazio", status_code=303)
    crud.create_opcao(db, categoria, nome)
    return RedirectResponse(f"/admin/opcoes/{categoria}?ok=add", status_code=303)


@router.post("/opcoes/{categoria}/{opcao_id}/editar")
async def opcoes_edit(
    request: Request,
    categoria: str,
    opcao_id: int,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if categoria not in OPCOES_CATEGORIAS:
        return RedirectResponse("/admin", status_code=303)
    form = dict((await request.form()))
    if not validate_csrf(request, form.get("csrf_token")):
        return RedirectResponse(f"/admin/opcoes/{categoria}", status_code=303)
    opcao = crud.get_opcao(db, opcao_id)
    if not opcao or opcao.categoria != categoria:
        return RedirectResponse(f"/admin/opcoes/{categoria}", status_code=303)
    novo_nome = (form.get("nome") or "").strip()
    if not novo_nome:
        return RedirectResponse(f"/admin/opcoes/{categoria}?err=vazio", status_code=303)
    resultado = crud.rename_opcao(db, opcao, novo_nome)
    if resultado is None:
        return RedirectResponse(f"/admin/opcoes/{categoria}?err=duplicado", status_code=303)
    return RedirectResponse(f"/admin/opcoes/{categoria}?ok=edit", status_code=303)


@router.post("/opcoes/{categoria}/{opcao_id}/toggle")
async def opcoes_toggle(
    request: Request,
    categoria: str,
    opcao_id: int,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if categoria not in OPCOES_CATEGORIAS:
        return RedirectResponse("/admin", status_code=303)
    form = dict((await request.form()))
    if not validate_csrf(request, form.get("csrf_token")):
        return RedirectResponse(f"/admin/opcoes/{categoria}", status_code=303)
    opcao = crud.get_opcao(db, opcao_id)
    if opcao and opcao.categoria == categoria:
        crud.toggle_opcao(db, opcao)
    return RedirectResponse(f"/admin/opcoes/{categoria}?ok=toggle", status_code=303)


@router.post("/opcoes/{categoria}/{opcao_id}/delete")
async def opcoes_delete(
    request: Request,
    categoria: str,
    opcao_id: int,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if categoria not in OPCOES_CATEGORIAS:
        return RedirectResponse("/admin", status_code=303)
    form = dict((await request.form()))
    if not validate_csrf(request, form.get("csrf_token")):
        return RedirectResponse(f"/admin/opcoes/{categoria}", status_code=303)
    opcao = crud.get_opcao(db, opcao_id)
    if opcao and opcao.categoria == categoria:
        crud.delete_opcao(db, opcao)
    return RedirectResponse(f"/admin/opcoes/{categoria}?ok=delete", status_code=303)
