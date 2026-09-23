"""Painel comercial: login, fila de cotacoes, formacao de preco, solicitacao
de frete -> Ordem de Coleta -> envio a Logistica, e Agenda de Carregamentos."""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import crud, emails
from app.constants import (
    ADMIN_TABS,
    AGENDA_STATUS_LABELS,
    OPCOES_CATEGORIAS,
    PAGADOR_OPCOES,
    PROXIMA_ACAO,
    STATUS_APROVADA,
    STATUS_EM_VALIDACAO,
    STATUS_FRETE_SOLICITADO,
    STATUS_NEGOCIACAO,
    STATUS_OC_EMITIDA,
    STATUS_REPROVADA,
    STATUS_RESPONDIDA,
    TIPOS_COTACAO_LABELS,
)
from app.database import get_db
from app.filiais import extrair_uf, label_empresa_cnpj, opcoes_empresa_cnpj
from app.forms import AgendaForm, ProposalForm, SolicitacaoFreteForm
from app.ordem_coleta_docx import build_ordem_coleta_docx
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
from app.utils import alerta_agenda, calc_seguro, format_valor, utcnow

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
            error="Sessão expirada. Tente novamente.",
        )
    username = (form.get("username") or "").strip()
    password = form.get("password") or ""
    if not check_admin_credentials(username, password):
        return render(
            request,
            "admin/login.html",
            next=nxt,
            csrf_token=get_csrf_token(request),
            error="Usuário ou senha inválidos.",
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
    empresa: str = "",
    tipo: str = "",
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if tab not in ADMIN_TABS:
        tab = "todas"
    quotes = crud.list_quotes(db, tab=tab, search=q, empresa=empresa, tipo=tipo)
    counts = {name: len(crud.list_quotes(db, tab=name)) for name in ADMIN_TABS}
    return render(
        request,
        "admin/lista.html",
        admin=admin,
        quotes=quotes,
        tab=tab,
        search=q,
        empresa=empresa,
        tipo=tipo,
        counts=counts,
        tipos_cotacao=TIPOS_COTACAO_LABELS,
        proxima_acao=PROXIMA_ACAO,
    )


# ----- Formacao de preco (FC -> margem -> FE + adicionais) ---------------

def _proposal_values(quote) -> dict:
    p = quote.proposal
    if not p:
        sugestao_seguro = format_valor(calc_seguro(quote.valor_nf)) if quote.valor_nf else ""
        return {"custo_seguro": sugestao_seguro}
    return {
        "custo_motorista": format_valor(p.custo_motorista),
        "custo_pedagio": format_valor(p.custo_pedagio),
        "custo_impostos": format_valor(p.custo_impostos),
        "custo_seguro": format_valor(p.custo_seguro),
        "custo_outros_internos": format_valor(p.custo_outros_internos),
        "margem_pct": format_valor(p.margem_pct),
        "valor_diaria": format_valor(p.valor_diaria),
        "valor_ajudante": format_valor(p.valor_ajudante),
        "valor_empilhadeira": format_valor(p.valor_empilhadeira),
        "valor_guincho": format_valor(p.valor_guincho),
        "custos_adicionais": format_valor(p.custos_adicionais),
        "custos_adicionais_desc": p.custos_adicionais_desc or "",
        "prazo_entrega": p.prazo_entrega,
        "validade": p.validade.isoformat(),
        "observacoes": p.observacoes,
    }


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
    return render(
        request,
        "admin/responder.html",
        admin=admin,
        quote=quote,
        historico=crud.list_proposal_history(db, quote.id),
        values=_proposal_values(quote),
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

    pf = ProposalForm(form)
    if not pf.validate():
        return render(
            request,
            "admin/responder.html",
            admin=admin,
            quote=quote,
            historico=crud.list_proposal_history(db, quote.id),
            values={**form},  # devolve o que o admin digitou, sem reformatar
            errors=pf.errors,
            today=utcnow().date().isoformat(),
            csrf_token=get_csrf_token(request),
        )

    crud.add_proposal(db, quote, pf.values, created_by=admin)
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
    if quote.status in (STATUS_RESPONDIDA, STATUS_NEGOCIACAO, STATUS_REPROVADA):
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
    if quote.status in (STATUS_RESPONDIDA, STATUS_NEGOCIACAO, STATUS_APROVADA):
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


# ----- Solicitacao de Frete -> Ordem de Coleta -> Logistica ---------------

@router.get("/cotacao/{code}/solicitacao")
def solicitacao_view(
    request: Request,
    code: str,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    quote = crud.get_quote_by_code(db, code)
    if not quote or not quote.solicitacao:
        return RedirectResponse("/admin", status_code=303)
    uf = extrair_uf(quote.destino_cidade)
    sugestao = crud.sugestao_empresa_cnpj_fila(db, uf)
    return render(
        request,
        "admin/solicitacao.html",
        admin=admin,
        quote=quote,
        solicitacao=quote.solicitacao,
        empresa_opcoes=opcoes_empresa_cnpj(),
        empresa_sugerida=sugestao,
        empresa_sugerida_label=label_empresa_cnpj(sugestao),
        uf_destino=uf,
        csrf_token=get_csrf_token(request),
    )


@router.post("/cotacao/{code}/solicitacao/validar")
async def solicitacao_validar(
    request: Request,
    code: str,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    quote = crud.get_quote_by_code(db, code)
    if not quote or not quote.solicitacao:
        return RedirectResponse("/admin", status_code=303)
    form = dict((await request.form()))
    if not validate_csrf(request, form.get("csrf_token")):
        return RedirectResponse(f"/admin/cotacao/{code}/solicitacao", status_code=303)
    uf = extrair_uf(quote.destino_cidade)
    escolha = crud.resolver_empresa_cnpj_oc(db, uf, form.get("empresa_cnpj"))
    if not escolha:
        return RedirectResponse(f"/admin/cotacao/{code}/solicitacao?err=empresa", status_code=303)
    if quote.status in (STATUS_FRETE_SOLICITADO, STATUS_EM_VALIDACAO) and not quote.ordem_coleta:
        empresa, cnpj = escolha
        oc = crud.gerar_ordem_coleta(
            db, quote, empresa=empresa, cnpj_filial=cnpj,
            uf_referencia=uf, gerado_por=admin,
        )
        emails.send_oc_emitida_interno(quote, oc)
    return RedirectResponse(f"/admin/cotacao/{code}/solicitacao?ok=oc", status_code=303)


@router.get("/cotacao/{code}/gerar-oc")
def gerar_oc_form(
    request: Request,
    code: str,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Atalho: gera a Ordem de Coleta direto de uma cotacao aprovada, sem
    esperar o cliente preencher a Solicitacao de Frete. Se ja houver uma
    solicitacao (cliente enviou), os dados vem pre-preenchidos."""
    quote = crud.get_quote_by_code(db, code)
    if not quote or quote.status != STATUS_APROVADA or quote.ordem_coleta:
        return RedirectResponse(f"/admin/cotacao/{code}", status_code=303)
    s = quote.solicitacao
    values = {
        "pagador": s.pagador if s else "", "pagador_documento": s.pagador_documento if s else "",
        "fornecedor_nome": s.fornecedor_nome if s else "", "fornecedor_contato": s.fornecedor_contato if s else "",
        "destinatario_nome": s.destinatario_nome if s else "", "destinatario_contato": s.destinatario_contato if s else "",
        "valor_nf": s.valor_nf if s else quote.valor_nf, "observacoes_operacionais": s.observacoes_operacionais if s else "",
    }
    uf = extrair_uf(quote.destino_cidade)
    sugestao = crud.sugestao_empresa_cnpj_fila(db, uf)
    return render(
        request, "admin/gerar_oc.html", admin=admin, quote=quote, values=values, errors={},
        pagador_opcoes=PAGADOR_OPCOES, empresa_opcoes=opcoes_empresa_cnpj(),
        empresa_sugerida=sugestao, empresa_sugerida_label=label_empresa_cnpj(sugestao),
        uf_destino=uf, csrf_token=get_csrf_token(request),
    )


@router.post("/cotacao/{code}/gerar-oc")
async def gerar_oc_submit(
    request: Request,
    code: str,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    quote = crud.get_quote_by_code(db, code)
    if not quote or quote.status != STATUS_APROVADA or quote.ordem_coleta:
        return RedirectResponse(f"/admin/cotacao/{code}", status_code=303)
    form = dict((await request.form()))
    if not validate_csrf(request, form.get("csrf_token")):
        return RedirectResponse(f"/admin/cotacao/{code}/gerar-oc", status_code=303)

    uf = extrair_uf(quote.destino_cidade)
    escolha = crud.resolver_empresa_cnpj_oc(db, uf, form.get("empresa_cnpj"))
    sf = SolicitacaoFreteForm(form)
    valida = sf.validate()
    if not escolha:
        valida = False
    if not valida:
        errors = dict(sf.errors)
        if not escolha:
            errors["empresa_cnpj"] = "Selecione a empresa/CNPJ da filial."
        sugestao = crud.sugestao_empresa_cnpj_fila(db, uf)
        return render(
            request, "admin/gerar_oc.html", admin=admin, quote=quote,
            values={**form}, errors=errors, pagador_opcoes=PAGADOR_OPCOES,
            empresa_opcoes=opcoes_empresa_cnpj(),
            empresa_sugerida=sugestao, empresa_sugerida_label=label_empresa_cnpj(sugestao),
            uf_destino=uf, csrf_token=get_csrf_token(request),
        )

    crud.create_or_update_solicitacao(db, quote, sf.values)
    empresa, cnpj = escolha
    oc = crud.gerar_ordem_coleta(
        db, quote, empresa=empresa, cnpj_filial=cnpj,
        uf_referencia=uf, gerado_por=admin,
    )
    emails.send_oc_emitida_interno(quote, oc)
    return RedirectResponse(f"/admin/cotacao/{code}/solicitacao?ok=oc", status_code=303)


@router.get("/cotacao/{code}/ordem-coleta.docx")
def baixar_ordem_coleta(
    request: Request,
    code: str,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    quote = crud.get_quote_by_code(db, code)
    if not quote or not quote.ordem_coleta:
        return RedirectResponse("/admin", status_code=303)
    conteudo = build_ordem_coleta_docx(quote)
    return Response(
        content=conteudo,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="ordem-coleta-{quote.ordem_coleta.numero}.docx"'
        },
    )


@router.post("/cotacao/{code}/solicitacao/devolver")
async def solicitacao_devolver(
    request: Request,
    code: str,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    quote = crud.get_quote_by_code(db, code)
    if not quote or not quote.solicitacao:
        return RedirectResponse("/admin", status_code=303)
    form = dict((await request.form()))
    if not validate_csrf(request, form.get("csrf_token")):
        return RedirectResponse(f"/admin/cotacao/{code}/solicitacao", status_code=303)
    motivo = (form.get("motivo") or "").strip()
    crud.devolver_solicitacao(db, quote, motivo)
    emails.send_solicitacao_devolvida_to_client(quote)
    return RedirectResponse(f"/admin/cotacao/{code}?ok=devolvida", status_code=303)


@router.post("/cotacao/{code}/enviar-logistica")
async def enviar_logistica(
    request: Request,
    code: str,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    quote = crud.get_quote_by_code(db, code)
    if not quote or not quote.ordem_coleta:
        return RedirectResponse("/admin", status_code=303)
    form = dict((await request.form()))
    if not validate_csrf(request, form.get("csrf_token")):
        return RedirectResponse(f"/admin/cotacao/{code}/solicitacao", status_code=303)
    if quote.status == STATUS_OC_EMITIDA and not quote.ordem_coleta.enviado_logistica_em:
        agenda = crud.enviar_logistica(db, quote, enviado_por=admin)
        emails.send_enviado_logistica_interno(quote, quote.ordem_coleta, agenda)
    return RedirectResponse(f"/admin/cotacao/{code}/solicitacao?ok=logistica", status_code=303)


# ----- Agenda de Carregamentos --------------------------------------------

def _month_bounds(mes: str | None) -> tuple[date, date, int, int]:
    hoje = utcnow().date()
    try:
        ano, mes_num = (int(p) for p in mes.split("-"))
    except (AttributeError, ValueError):
        ano, mes_num = hoje.year, hoje.month
    primeiro = date(ano, mes_num, 1)
    ultimo_dia = calendar.monthrange(ano, mes_num)[1]
    ultimo = date(ano, mes_num, ultimo_dia)
    return primeiro, ultimo, ano, mes_num


@router.get("/agenda")
def agenda_list(
    request: Request,
    view: str = "lista",
    status: str = "",
    mes: str = "",
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if view == "calendario":
        primeiro, ultimo, ano, mes_num = _month_bounds(mes)
        itens = crud.list_agenda(db, status=status, inicio=primeiro, fim=ultimo)
        semanas = calendar.Calendar(firstweekday=6).monthdatescalendar(ano, mes_num)
        por_dia: dict[date, list] = {}
        for item in itens:
            por_dia.setdefault(item.data_carregamento, []).append(item)
        prev_mes = (primeiro - timedelta(days=1)).strftime("%Y-%m")
        next_mes = (ultimo + timedelta(days=1)).strftime("%Y-%m")
        return render(
            request, "admin/agenda.html", admin=admin, view=view, status=status,
            semanas=semanas, por_dia=por_dia, mes_atual=primeiro,
            prev_mes=prev_mes, next_mes=next_mes, hoje=utcnow().date(),
            agenda_status_labels=AGENDA_STATUS_LABELS,
        )

    itens = crud.list_agenda(db, status=status)
    itens_com_alerta = [
        (item, alerta_agenda(item.data_carregamento, status_agenda=item.status_agenda))
        for item in itens
    ]
    return render(
        request, "admin/agenda.html", admin=admin, view=view, status=status,
        itens=itens_com_alerta, agenda_status_labels=AGENDA_STATUS_LABELS,
        hoje=utcnow().date(),
    )


@router.get("/agenda/{agenda_id}")
def agenda_item_view(
    request: Request,
    agenda_id: int,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    item = crud.get_agenda_item(db, agenda_id)
    if not item:
        return RedirectResponse("/admin/agenda", status_code=303)
    values = {
        "data_carregamento": item.data_carregamento.isoformat(),
        "hora_prevista": item.hora_prevista or "",
        "responsavel_logistica": item.responsavel_logistica or "",
        "status_agenda": item.status_agenda,
        "confirmado": "sim" if item.confirmado else "nao",
        "observacoes": item.observacoes or "",
    }
    return render(
        request, "admin/agenda_item.html", admin=admin, item=item, values=values, errors={},
        agenda_status_labels=AGENDA_STATUS_LABELS,
        alerta=alerta_agenda(item.data_carregamento, status_agenda=item.status_agenda),
        csrf_token=get_csrf_token(request),
    )


@router.post("/agenda/{agenda_id}")
async def agenda_item_update(
    request: Request,
    agenda_id: int,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    item = crud.get_agenda_item(db, agenda_id)
    if not item:
        return RedirectResponse("/admin/agenda", status_code=303)
    form = dict((await request.form()))
    if not validate_csrf(request, form.get("csrf_token")):
        return RedirectResponse(f"/admin/agenda/{agenda_id}", status_code=303)

    af = AgendaForm(form)
    if not af.validate():
        return render(
            request, "admin/agenda_item.html", admin=admin, item=item,
            values={**form}, errors=af.errors, agenda_status_labels=AGENDA_STATUS_LABELS,
            alerta=alerta_agenda(item.data_carregamento, status_agenda=item.status_agenda),
            csrf_token=get_csrf_token(request),
        )
    crud.update_agenda(db, item, af.values)
    return RedirectResponse("/admin/agenda?ok=1", status_code=303)


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
