from datetime import date, timedelta
from decimal import Decimal

from app.constants import AGENDA_CANCELADO, AGENDA_CARREGADO
from app.database import SessionLocal
from app.utils import (
    alerta_agenda,
    build_mensagem_logistica,
    format_brl,
    format_cnpj_cpf,
    gen_oc_numero,
    gen_quote_code,
    normalize_cep,
    parse_brl,
)


def test_parse_brl_ptbr():
    assert parse_brl("25.000,00") == Decimal("25000.00")
    assert parse_brl("R$ 1.234,56") == Decimal("1234.56")
    assert parse_brl("1234") == Decimal("1234.00")
    assert parse_brl("1234.56") == Decimal("1234.56")
    assert parse_brl("") is None
    assert parse_brl(None) is None
    assert parse_brl("abc") is None


def test_parse_brl_ponto_como_milhar():
    # "dois mil" digitado a brasileira nao pode virar R$ 2 nem R$ 200.000
    assert parse_brl("2.000") == Decimal("2000.00")
    assert parse_brl("12.500") == Decimal("12500.00")
    assert parse_brl("2.000.000") == Decimal("2000000.00")
    # valor cru vindo de Decimal continua sendo lido certo
    assert parse_brl("2000.00") == Decimal("2000.00")
    assert parse_brl("200000.00") == Decimal("200000.00")
    # ponto decimal legitimo preservado
    assert parse_brl("2.5") == Decimal("2.50")


def test_format_brl():
    assert format_brl(Decimal("25000")) == "R$ 25.000,00"
    assert format_brl(Decimal("1234.5")) == "R$ 1.234,50"
    assert format_brl(0) == "R$ 0,00"
    assert format_brl(None) == "-"


def test_normalize_cep():
    assert normalize_cep("80010000") == "80010-000"
    assert normalize_cep("80010-000") == "80010-000"
    assert normalize_cep("") is None


def test_gen_quote_code_increments():
    db = SessionLocal()
    try:
        assert gen_quote_code(db, year=2025) == "COT-2025-000001"
    finally:
        db.close()


def test_gen_oc_numero_increments():
    """AMG-J-<sequencial continuo>, sem reset por ano -- so soma o total de
    OCs ja emitidas."""
    db = SessionLocal()
    try:
        assert gen_oc_numero(db) == "AMG-J-1"
    finally:
        db.close()


def test_format_cnpj_cpf():
    assert format_cnpj_cpf("12345678900") == "123.456.789-00"
    assert format_cnpj_cpf("12345678000190") == "12.345.678/0001-90"
    # ja formatado -- reformata igual (idempotente)
    assert format_cnpj_cpf("123.456.789-00") == "123.456.789-00"
    assert format_cnpj_cpf("12.345.678/0001-90") == "12.345.678/0001-90"
    # nem 11 nem 14 digitos -- devolve original limpo, sem inventar formato
    assert format_cnpj_cpf("123") == "123"
    assert format_cnpj_cpf(None) is None
    assert format_cnpj_cpf("") is None


def test_build_mensagem_logistica():
    from datetime import date
    from decimal import Decimal
    from types import SimpleNamespace

    proposal = SimpleNamespace(fc=Decimal("9800.00"))
    quote = SimpleNamespace(
        tipo_veiculo="Carreta Sider", carroceria="Grade baixa",
        tipo_material="Andaime", descricao_material=None,
        peso_total="5.000 kg", origem_cidade="Curitiba - PR",
        destino_cidade="Londrina - PR", data_coleta=date(2026, 10, 10),
        proposal=proposal,
    )
    msg = build_mensagem_logistica(quote)
    assert "1 x Carreta Sider - Grade baixa" in msg
    assert "Andaime" in msg
    assert "5.000 kg" in msg
    assert "Curitiba - PR X Londrina - PR" in msg
    assert "R$ 9.800,00" in msg  # FC, sem margem
    assert "*Carregamento dia 10/10/2026*" in msg


def test_alerta_agenda():
    hoje = date.today()
    assert alerta_agenda(hoje) == "HOJE"
    assert alerta_agenda(hoje + timedelta(days=1)) == "AMANHÃ"
    assert alerta_agenda(hoje + timedelta(days=5)) == "PRÓXIMO"
    assert alerta_agenda(hoje + timedelta(days=10)) is None
    assert alerta_agenda(hoje - timedelta(days=1)) == "ATRASADO"
    # concluido/cancelado nao gera alerta de atraso
    assert alerta_agenda(hoje - timedelta(days=1), status_agenda=AGENDA_CARREGADO) is None
    assert alerta_agenda(hoje - timedelta(days=1), status_agenda=AGENDA_CANCELADO) is None
    assert alerta_agenda(None) is None
