"""Utilidades: codigo de cotacao, moeda pt-BR, CEP, calculo de seguro."""

import re
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from sqlalchemy import func
from sqlalchemy.orm import Session

TWO_PLACES = Decimal("0.01")
SEGURO_ALIQUOTA = Decimal("0.002")  # 0,2% do valor da NF


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def gen_quote_code(db: Session, *, year: int | None = None) -> str:
    """Gera COT-<ano>-<sequencial de 6 digitos> com base na contagem do ano."""
    from app.models import Quote

    year = year or utcnow().year
    prefix = f"COT-{year}-"
    count = (
        db.query(func.count(Quote.id))
        .filter(Quote.code.like(f"{prefix}%"))
        .scalar()
        or 0
    )
    return f"{prefix}{count + 1:06d}"


def parse_brl(value: str | None) -> Decimal | None:
    """Converte '25.000,00', 'R$ 1.234,56', '1234.56' ou '1234' em Decimal."""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    raw = raw.replace("R$", "").replace(" ", "").replace(" ", "")
    if "," in raw:
        # Formato pt-BR: ponto e separador de milhar, virgula e decimal.
        raw = raw.replace(".", "").replace(",", ".")
    # Caso contrario assume ponto decimal (ou inteiro).
    try:
        return Decimal(raw).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None


def _group_thousands(digits: str) -> str:
    grupos = []
    while len(digits) > 3:
        grupos.insert(0, digits[-3:])
        digits = digits[:-3]
    grupos.insert(0, digits)
    return ".".join(grupos)


def format_brl(value: Decimal | float | int | None) -> str:
    """Formata como 'R$ 25.000,00'."""
    if value is None:
        return "-"
    dec = Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    inteiro, _, centavos = f"{abs(dec):.2f}".partition(".")
    sinal = "-" if dec < 0 else ""
    return f"{sinal}R$ {_group_thousands(inteiro)},{centavos}"


def parse_peso(value: str | None) -> Decimal | None:
    """Converte um peso em kg digitado livremente ('5.000', '5000', '5.000,5',
    '5000 kg') em Decimal. Sem virgula, os pontos sao separadores de milhar
    (peso em kg raramente tem casas decimais)."""
    if value is None:
        return None
    raw = str(value).strip().lower().replace("kg", "").strip().replace(" ", "")
    if not raw:
        return None
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    else:
        raw = raw.replace(".", "")
    try:
        return Decimal(raw).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None


def format_peso(value: Decimal | float | int | None) -> str:
    """Formata um peso em kg: '5.000' ou '5.000,5' (casas decimais so quando existem)."""
    if value is None:
        return "-"
    dec = Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    inteiro, _, centavos = f"{abs(dec):.2f}".partition(".")
    texto = _group_thousands(inteiro)
    if centavos != "00":
        texto += "," + centavos.rstrip("0")
    return texto


def calc_seguro(valor_nf: Decimal | None) -> Decimal:
    if not valor_nf:
        return Decimal("0.00")
    return (Decimal(valor_nf) * SEGURO_ALIQUOTA).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP
    )


_CEP_RE = re.compile(r"\D")


def normalize_cep(value: str | None) -> str | None:
    """Mantem apenas digitos e devolve no formato 00000-000 quando possivel."""
    if not value:
        return None
    digits = _CEP_RE.sub("", str(value))
    if not digits:
        return None
    if len(digits) == 8:
        return f"{digits[:5]}-{digits[5:]}"
    return digits


def parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    raw = _CEP_RE.sub("", str(value))
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None
