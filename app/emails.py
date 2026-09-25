"""Envio de e-mails via Resend. Sem RESEND_API_KEY, imprime no console (dev)."""

from __future__ import annotations

import logging

from app.config import settings
from app.constants import STATUS_LABELS
from app.models import AgendaCarregamento, OrdemColeta, Quote, SolicitacaoFrete
from app.security import sign_quote_token
from app.utils import format_brl

logger = logging.getLogger("amg.emails")

_resend = None
if settings.resend_api_key:
    try:
        import resend as _resend_mod

        _resend_mod.api_key = settings.resend_api_key
        _resend = _resend_mod
    except ImportError:  # pragma: no cover
        logger.warning("pacote 'resend' nao instalado; e-mails irao para o console")


def _send(
    to: str,
    subject: str,
    html: str,
    attachments: list[tuple[str, bytes]] | None = None,
    cc: str | list[str] | None = None,
) -> None:
    cc_list = [cc] if isinstance(cc, str) else (cc or [])
    if settings.email_destino:
        # Sem dominio verificado no Resend, a conta so entrega pro proprio
        # dono -- redireciona tudo pra ca (com o destinatario real anotado
        # no assunto) em vez de deixar o envio falhar/nunca chegar.
        reais = ", ".join([to, *cc_list]) if cc_list else to
        subject = f"[Para: {reais}] {subject}"
        to = settings.email_destino
        cc_list = []
    if _resend is None:
        extra = ""
        if cc_list:
            extra += f"\nCc: {', '.join(cc_list)}"
        if attachments:
            extra += "\nAnexos: " + ", ".join(
                f"{name} ({len(data)} bytes)" for name, data in attachments
            )
        print(
            f"\n----- E-MAIL (dev) -----\nPara: {to}\nAssunto: {subject}{extra}\n\n{html}\n"
            "-----------------------",
            flush=True,
        )
        return
    try:
        params = {
            "from": settings.email_from,
            "to": [to],
            "subject": subject,
            "html": html,
        }
        if cc_list:
            params["cc"] = cc_list
        if attachments:
            params["attachments"] = [
                {"filename": name, "content": list(data)} for name, data in attachments
            ]
        _resend.Emails.send(params)
    except Exception as exc:  # pragma: no cover - falha de rede nao quebra o fluxo
        logger.error("Falha ao enviar e-mail para %s: %s", to, exc)


def _quote_link(quote: Quote) -> str:
    token = sign_quote_token(quote.code)
    return f"{settings.base_url}/cotacao/{quote.code}?t={token}"


def _admin_link(quote: Quote) -> str:
    return f"{settings.base_url}/admin/cotacao/{quote.code}"


def _row(label: str, value: str) -> str:
    return (
        f'<tr><td style="padding:4px 12px 4px 0;color:#5b6472">{label}</td>'
        f'<td style="padding:4px 0"><strong>{value}</strong></td></tr>'
    )


def _table(*rows: str) -> str:
    return f'<table style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:14px">{"".join(rows)}</table>'


def send_quote_to_comercial(quote: Quote) -> None:
    sn = {True: "Sim", False: "Não"}
    html = f"""
    <h2>Nova solicitação de cotação — {quote.code}</h2>
    {_table(
        _row("Comprador", quote.client_name),
        _row("Empresa", quote.client_company or "-"),
        _row("CNPJ/CPF", quote.client_cnpj or "-"),
        _row("E-mail", quote.client_email or "-"),
        _row("Telefone", quote.client_phone or "-"),
        _row("Origem", f"{quote.origem_cidade} — CEP {quote.origem_cep or '-'} — {quote.origem_endereco or '-'} — {quote.origem_bairro or '-'}"),
        _row("Destino", f"{quote.destino_cidade} — CEP {quote.destino_cep or '-'} — {quote.destino_endereco or '-'} — {quote.destino_bairro or '-'}"),
        _row("Tipo de material", quote.tipo_material),
        _row("Descrição", quote.descricao_material or "-"),
        _row("Volumes", str(quote.qtd_volumes) if quote.qtd_volumes else "-"),
        _row("Dimensões", quote.dimensoes or "-"),
        _row("Peso total", quote.peso_total or "-"),
        _row("Valor da NF", format_brl(quote.valor_nf)),
        _row("Diária", sn[bool(quote.servico_diaria)]),
        _row("Ajudante", sn[bool(quote.servico_ajudante)] + (f" ({quote.ajudante_qtd})" if quote.ajudante_qtd else "")),
        _row("Empilhadeira", sn[bool(quote.servico_empilhadeira)]),
        _row("Guincho/Munck", sn[bool(quote.servico_guincho)]),
        _row("Veículo desejado", quote.tipo_veiculo or "-"),
        _row("Carroceria", quote.carroceria or "-"),
        _row("Capacidade aprox.", quote.capacidade_aprox or "-"),
        _row("Data prevista de coleta", quote.data_coleta.strftime("%d/%m/%Y")),
        _row("Data desejada de entrega", quote.data_entrega.strftime("%d/%m/%Y") if quote.data_entrega else "-"),
        _row("Observações", quote.observacoes or "-"),
    )}
    <p><a href="{_admin_link(quote)}">Abrir no painel comercial</a></p>
    """
    _send(settings.email_comercial, f"Nova cotação {quote.code}", html)


def send_confirmation_to_client(quote: Quote) -> None:
    if not quote.client_email:
        return  # cliente nao informou e-mail -- nao ha pra quem avisar
    html = f"""
    <h2>Recebemos a sua solicitação de cotação</h2>
    <p>Olá, {quote.client_name}!</p>
    <p>Sua cotação <strong>{quote.code}</strong> foi recebida e será analisada pelo nosso time.
    Você receberá o retorno em breve por e-mail e por aqui.</p>
    <p>Rota: <strong>{quote.origem_cidade} &rarr; {quote.destino_cidade}</strong></p>
    <p><a href="{_quote_link(quote)}">Acompanhar a cotação</a></p>
    """
    _send(quote.client_email, f"Cotação {quote.code} recebida — AMG Logística", html)


def send_decision_to_client(quote: Quote) -> None:
    """Avisa o cliente quando o ADMIN registra manualmente aprovação/reprovação
    (ex.: cliente decidiu por telefone)."""
    if not quote.client_email:
        return  # cliente nao informou e-mail -- nao ha pra quem avisar
    label = STATUS_LABELS.get(quote.status, quote.status)
    if quote.status == "aprovada":
        corpo = (
            "<p>Boa notícia! Sua cotação foi <strong>aprovada</strong> pela AMG. "
            "Agora é só preencher a Solicitação de Frete para darmos sequência.</p>"
        )
    else:
        motivo = (
            f"<p><strong>Motivo:</strong> {quote.decision_note}</p>"
            if quote.decision_note
            else ""
        )
        corpo = f"<p>Sua cotação foi <strong>reprovada</strong>.</p>{motivo}"
    html = f"""
    <h2>Cotação {quote.code}: {label}</h2>
    <p>Olá, {quote.client_name}!</p>
    <p>Rota: <strong>{quote.origem_cidade} &rarr; {quote.destino_cidade}</strong></p>
    {corpo}
    <p><a href="{_quote_link(quote)}">Ver a cotação no site</a></p>
    """
    _send(quote.client_email, f"Cotação {quote.code}: {label}", html)


def send_solicitacao_to_comercial(quote: Quote, solicitacao: SolicitacaoFrete) -> None:
    html = f"""
    <h2>Solicitação de Frete enviada — cotação {quote.code}</h2>
    {_table(
        _row("Comprador", quote.client_name),
        _row("Empresa", quote.client_company or "-"),
        _row("Pagador", solicitacao.pagador),
        _row("CNPJ/CPF do pagador", solicitacao.pagador_documento),
        _row("Fornecedor/remetente", solicitacao.fornecedor_nome),
        _row("Destinatário", solicitacao.destinatario_nome),
        _row("Valor da NF", format_brl(solicitacao.valor_nf)),
        _row("Observações operacionais", solicitacao.observacoes_operacionais or "-"),
    )}
    <p><a href="{_admin_link(quote)}">Validar e gerar Ordem de Coleta</a></p>
    """
    _send(settings.email_comercial, f"Solicitação de frete — cotação {quote.code}", html)


def send_solicitacao_devolvida_to_client(quote: Quote) -> None:
    if not quote.client_email:
        return  # cliente nao informou e-mail -- nao ha pra quem avisar
    html = f"""
    <h2>Solicitação de frete devolvida — cotação {quote.code}</h2>
    <p>Olá, {quote.client_name}! Sua solicitação de frete precisa de um ajuste antes de
    seguirmos com a Ordem de Coleta.</p>
    <p><strong>Motivo:</strong> {quote.decision_note or "-"}</p>
    <p><a href="{_quote_link(quote)}">Reenviar a solicitação</a></p>
    """
    _send(quote.client_email, f"Solicitação de frete — ajuste necessário ({quote.code})", html)


def send_oc_emitida_interno(quote: Quote, oc: OrdemColeta) -> None:
    html = f"""
    <h2>Ordem de Coleta {oc.numero} emitida — cotação {quote.code}</h2>
    <p>{quote.client_company or quote.client_name} — {quote.origem_cidade} &rarr; {quote.destino_cidade}</p>
    <p><a href="{_admin_link(quote)}">Ver cotação</a></p>
    """
    _send(settings.email_comercial, f"OC {oc.numero} emitida — cotação {quote.code}", html)


def send_enviado_logistica_interno(quote: Quote, oc: OrdemColeta, agenda: AgendaCarregamento) -> None:
    # O CC volta a funcionar normalmente quando settings.email_destino nao
    # estiver setado (dominio verificado no Resend) -- ate la, _send()
    # redireciona para/cc pro mesmo lugar, entao nao ha risco do Resend
    # rejeitar o envio por causa do CC de outro dominio.
    html = f"""
    <h2>OC {oc.numero} enviada à Logística — cotação {quote.code}</h2>
    <p>Carregamento previsto: {agenda.data_carregamento.strftime('%d/%m/%Y')}</p>
    <p>Já consta na Agenda de Carregamentos.</p>
    """
    _send(
        settings.email_logistica,
        f"OC {oc.numero} enviada à Logística",
        html,
        cc=settings.email_logistica_cc,
    )
