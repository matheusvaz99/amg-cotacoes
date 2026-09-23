from datetime import date, timedelta
from decimal import Decimal

from app.constants import AGENDA_CANCELADO, AGENDA_CARREGADO
from app.database import SessionLocal
from app.utils import (
    alerta_agenda,
    calc_seguro,
    format_brl,
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


def test_calc_seguro():
    assert calc_seguro(Decimal("25000.00")) == Decimal("50.00")
    assert calc_seguro(Decimal("14000.00")) == Decimal("28.00")
    assert calc_seguro(None) == Decimal("0.00")


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
