"""Envio de e-mails via Resend. Sem RESEND_API_KEY, imprime no console (dev)."""

from __future__ import annotations

import logging

from app.config import settings
from app.constants import STATUS_LABELS
from app.models import Proposal, Quote
from app.security import sign_quote_token
from app.utils import format_brl, format_peso

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
) -> None:
    if _resend is None:
        extra = ""
        if attachments:
            extra = "\nAnexos: " + ", ".join(
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


def send_quote_to_comercial(quote: Quote) -> None:
    sim_nao = {True: "Sim", False: "Nao"}
    html = f"""
    <h2>Nova solicitacao de cotacao — {quote.code}</h2>
    <table style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:14px">
      {_row("Cliente", quote.client_name)}
      {_row("E-mail", quote.client_email)}
      {_row("Telefone", quote.client_phone or "-")}
      {_row("Origem", f"{quote.origem_cidade} — CEP {quote.origem_cep or '-'} — {quote.origem_endereco or '-'} — {quote.origem_bairro or '-'}")}
      {_row("Destino", f"{quote.destino_cidade} — CEP {quote.destino_cep or '-'} — {quote.destino_endereco or '-'} — {quote.destino_bairro or '-'}")}
      {_row("Tipo de material", quote.tipo_material)}
      {_row("Descricao", quote.descricao_material or "-")}
      {_row("Volumes", str(quote.qtd_volumes))}
      {_row("Peso total (kg)", format_peso(quote.peso_total_kg))}
      {_row("Valor da NF", format_brl(quote.valor_nf))}
      {_row("Servico de carga", sim_nao[quote.servico_carga])}
      {_row("Servico de descarga", sim_nao[quote.servico_descarga])}
      {_row("Veiculo desejado", quote.tipo_veiculo)}
      {_row("Carroceria", quote.carroceria or "-")}
      {_row("Capacidade aprox.", quote.capacidade_aprox)}
      {_row("Data prevista de coleta", quote.data_coleta.strftime("%d/%m/%Y"))}
      {_row("Observacoes", quote.observacoes or "-")}
    </table>
    <p><a href="{_admin_link(quote)}">Abrir no painel comercial</a></p>
    """
    _send(settings.email_comercial, f"Nova cotacao {quote.code}", html)


def send_confirmation_to_client(quote: Quote) -> None:
    html = f"""
    <h2>Recebemos a sua solicitacao de cotacao</h2>
    <p>Ola, {quote.client_name}!</p>
    <p>Sua cotacao <strong>{quote.code}</strong> foi recebida e sera analisada pelo nosso time.
    Voce recebera o retorno em breve por e-mail e por aqui.</p>
    <p>Rota: <strong>{quote.origem_cidade} &rarr; {quote.destino_cidade}</strong></p>
    <p><a href="{_quote_link(quote)}">Acompanhar a cotacao</a></p>
    """
    _send(quote.client_email, f"Cotacao {quote.code} recebida — AMG Logistica", html)


def send_proposal_ready(quote: Quote, proposal: Proposal) -> None:
    html = f"""
    <h2>Sua cotacao {quote.code} foi respondida</h2>
    <p>Ola, {quote.client_name}! Preparamos a proposta para a rota
    <strong>{quote.origem_cidade} &rarr; {quote.destino_cidade}</strong>.</p>
    <table style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:14px">
      {_row("Frete", format_brl(proposal.frete))}
      {_row("Pedagio", format_brl(proposal.pedagio))}
      {_row("Seguro (0,2%)", format_brl(proposal.seguro))}
      {_row("Total", format_brl(proposal.total))}
      {_row("Prazo de entrega", proposal.prazo_entrega)}
      {_row("Validade da proposta", proposal.validade.strftime("%d/%m/%Y"))}
    </table>
    <p><a href="{_quote_link(quote)}">Ver proposta completa e responder</a></p>
    """
    _send(quote.client_email, f"Proposta pronta — cotacao {quote.code}", html)


def send_quote_pdf_to_client(quote: Quote, pdf_bytes: bytes) -> None:
    """Envia ao cliente a cotacao em PDF (anexo), disparado pelo painel comercial."""
    proposal = quote.proposal
    resumo = ""
    if proposal is not None:
        resumo = (
            '<table style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:14px">'
            f'{_row("Total", format_brl(proposal.total))}'
            f'{_row("Prazo de entrega", proposal.prazo_entrega)}'
            f'{_row("Validade da proposta", proposal.validade.strftime("%d/%m/%Y"))}'
            "</table>"
        )
    html = f"""
    <h2>Cotacao {quote.code} — AMG Logistica</h2>
    <p>Ola, {quote.client_name}! Segue em anexo a cotacao de frete para a rota
    <strong>{quote.origem_cidade} &rarr; {quote.destino_cidade}</strong>.</p>
    {resumo}
    <p><a href="{_quote_link(quote)}">Ver a cotacao no site</a></p>
    <p style="color:#5b6472;font-size:12px">As cotacoes sao estimativas e nao geram reserva de veiculo.
    Valores validos conforme o prazo informado na proposta.</p>
    """
    _send(
        quote.client_email,
        f"Cotacao {quote.code} — AMG Logistica",
        html,
        attachments=[(f"cotacao-{quote.code}.pdf", pdf_bytes)],
    )


def send_client_decision(quote: Quote) -> None:
    label = STATUS_LABELS.get(quote.status, quote.status)
    extra = ""
    if quote.client_decision_note:
        extra = f"<p><strong>Observacao do cliente:</strong><br>{quote.client_decision_note}</p>"
    html = f"""
    <h2>Cotacao {quote.code}: {label}</h2>
    <p>Cliente: {quote.client_name} ({quote.client_email})</p>
    <p>Rota: {quote.origem_cidade} &rarr; {quote.destino_cidade}</p>
    {extra}
    <p><a href="{_admin_link(quote)}">Abrir no painel comercial</a></p>
    """
    _send(settings.email_comercial, f"Cotacao {quote.code}: {label}", html)
