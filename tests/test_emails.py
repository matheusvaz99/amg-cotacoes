"""Testes de app/emails.py: suporte a copia (cc), o aviso interno de OC
enviada a Logistica, e o redirecionamento via EMAIL_DESTINO (workaround
enquanto nenhum dominio proprio estiver verificado no Resend -- sem isso a
conta so entrega e-mail pro proprio dono da conta, rejeitando qualquer
outro destinatario)."""

from datetime import date
from types import SimpleNamespace

from app import emails
from app.config import settings


def test_send_console_dev_mostra_cc_string(capsys):
    emails._send("dest@x.com", "Assunto", "<p>corpo</p>", cc="copia@x.com")
    out = capsys.readouterr().out
    assert "Para: dest@x.com" in out
    assert "Cc: copia@x.com" in out


def test_send_console_dev_mostra_cc_lista(capsys):
    emails._send("dest@x.com", "Assunto", "<p>corpo</p>", cc=["a@x.com", "b@x.com"])
    out = capsys.readouterr().out
    assert "Cc: a@x.com, b@x.com" in out


def test_send_console_dev_sem_cc_nao_mostra_linha(capsys):
    emails._send("dest@x.com", "Assunto", "<p>corpo</p>")
    out = capsys.readouterr().out
    assert "Cc:" not in out


def test_send_enviado_logistica_interno_usa_email_logistica_e_cc(monkeypatch):
    captured = {}

    def fake_send(to, subject, html, attachments=None, cc=None):
        captured["to"] = to
        captured["cc"] = cc
        captured["subject"] = subject
        captured["html"] = html

    monkeypatch.setattr(emails, "_send", fake_send)

    quote = SimpleNamespace(code="COT-2026-000001")
    oc = SimpleNamespace(numero="OC-2026-000001")
    agenda = SimpleNamespace(data_carregamento=date(2026, 10, 10))

    emails.send_enviado_logistica_interno(quote, oc, agenda)

    assert captured["to"] == settings.email_logistica
    assert captured["cc"] == settings.email_logistica_cc
    assert "OC-2026-000001" in captured["subject"]
    assert "COT-2026-000001" in captured["html"]


# ----- EMAIL_DESTINO: redireciona tudo pro dono da conta Resend ------------

def test_send_sem_email_destino_nao_redireciona(monkeypatch, capsys):
    monkeypatch.setattr(settings, "email_destino", "")
    emails._send("cliente@dominio-qualquer.com.br", "Assunto original", "<p>corpo</p>")
    out = capsys.readouterr().out
    assert "Para: cliente@dominio-qualquer.com.br" in out
    assert "Assunto: Assunto original" in out
    assert "[Para:" not in out


def test_send_com_email_destino_redireciona_to_e_anota_no_assunto(monkeypatch, capsys):
    monkeypatch.setattr(settings, "email_destino", "dono@conta-resend.com")
    emails._send("cliente@dominio-qualquer.com.br", "Assunto original", "<p>corpo</p>")
    out = capsys.readouterr().out
    assert "Para: dono@conta-resend.com" in out
    assert "[Para: cliente@dominio-qualquer.com.br] Assunto original" in out


def test_send_com_email_destino_inclui_cc_original_no_assunto_e_derruba_cc(monkeypatch, capsys):
    monkeypatch.setattr(settings, "email_destino", "dono@conta-resend.com")
    emails._send(
        "cliente@dominio-qualquer.com.br", "Assunto", "<p>corpo</p>", cc="copia@outrodominio.com",
    )
    out = capsys.readouterr().out
    assert "Para: dono@conta-resend.com" in out
    assert "[Para: cliente@dominio-qualquer.com.br, copia@outrodominio.com] Assunto" in out
    assert "Cc:" not in out  # cc derrubado -- so o "to" real vai anotado no assunto
