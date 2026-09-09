"""Envio de e-mails via Resend. Sem RESEND_API_KEY, imprime no console (dev)."""

from __future__ import annotations

import logging

from app.config import settings
from app.constants import STATUS_LABELS
from app.models import Quote
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
    sn = {True: "Sim", False: "Nao"}
    html = f"""
    <h2>Nova solicitacao de cotacao — {quote.code}</h2>
    <table style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:14px">
      {_row("Comprador", quote.client_name)}
      {_row("Empresa", quote.client_company or "-")}
      {_row("E-mail", quote.client_email)}
      {_row("Telefone", quote.client_phone or "-")}
      {_row("Origem", f"{quote.origem_cidade} — CEP {quote.origem_cep or '-'} — {quote.origem_endereco or '-'} — {quote.origem_bairro or '-'}")}
      {_row("Destino", f"{quote.destino_cidade} — CEP {quote.destino_cep or '-'} — {quote.destino_endereco or '-'} — {quote.destino_bairro or '-'}")}
      {_row("Tipo de material", quote.tipo_material)}
      {_row("Descricao", quote.descricao_material or "-")}
      {_row("Volumes", str(quote.qtd_volumes))}
      {_row("Peso total (kg)", format_peso(quote.peso_total_kg))}
      {_row("Valor da NF", format_brl(quote.valor_nf))}
      {_row("Servico de carga", sn[quote.servico_carga])}
      {_row("Servico de descarga", sn[quote.servico_descarga])}
      {_row("Necessita diaria", sn[bool(quote.servico_diaria)])}
      {_row("Necessita guincho", sn[bool(quote.servico_guincho)])}
      {_row("Veiculo desejado", quote.tipo_veiculo)}
      {_row("Carroceria", quote.carroceria or "-")}
      {_row("Capacidade aprox.", quote.capacidade_aprox)}
      {_row("Data prevista de coleta", quote.data_coleta.strftime("%d/%m/%Y"))}
      {_row("Data desejada de entrega", quote.data_entrega.strftime("%d/%m/%Y") if quote.data_entrega else "-")}
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


def send_decision_to_client(quote: Quote) -> None:
    """Avisa o cliente que a AMG aprovou ou reprovou a cotacao."""
    label = STATUS_LABELS.get(quote.status, quote.status)
    if quote.status == "aprovada":
        corpo = (
            "<p>Boa noticia! Sua cotacao foi <strong>aprovada</strong> pela AMG. "
            "Nosso time comercial dara sequencia ao processo e podera entrar em contato.</p>"
        )
    else:
        motivo = (
            f"<p><strong>Motivo:</strong> {quote.decision_note}</p>"
            if quote.decision_note
            else ""
        )
        corpo = (
            f"<p>Sua cotacao foi <strong>reprovada</strong>.</p>{motivo}"
            "<p>Se quiser, solicite uma nova cotacao pelo site.</p>"
        )
    html = f"""
    <h2>Cotacao {quote.code}: {label}</h2>
    <p>Ola, {quote.client_name}!</p>
    <p>Rota: <strong>{quote.origem_cidade} &rarr; {quote.destino_cidade}</strong></p>
    {corpo}
    <p><a href="{_quote_link(quote)}">Ver a cotacao no site</a></p>
    """
    _send(quote.client_email, f"Cotacao {quote.code}: {label}", html)
