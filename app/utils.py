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


def _gen_sequential_code(db: Session, model, code_attr: str, prefix_base: str, *, year: int | None = None) -> str:
    """Gera <prefixo>-<ano>-<sequencial de 6 digitos> contando os registros do ano."""
    year = year or utcnow().year
    prefix = f"{prefix_base}-{year}-"
    column = getattr(model, code_attr)
    count = db.query(func.count(getattr(model, "id"))).filter(column.like(f"{prefix}%")).scalar() or 0
    return f"{prefix}{count + 1:06d}"


def gen_quote_code(db: Session, *, year: int | None = None) -> str:
    """Gera COT-<ano>-<sequencial de 6 digitos> com base na contagem do ano."""
    from app.models import Quote

    return _gen_sequential_code(db, Quote, "code", "COT", year=year)


def gen_oc_numero(db: Session, *, year: int | None = None) -> str:
    """Gera OC-<ano>-<sequencial de 6 digitos> para a Ordem de Coleta."""
    from app.models import OrdemColeta

    return _gen_sequential_code(db, OrdemColeta, "numero", "OC", year=year)


def parse_brl(value: str | None) -> Decimal | None:
    """Converte valores em dinheiro digitados de varias formas em Decimal:

    '25.000,00', 'R$ 1.234,56', '2000.00', '1234'  -> ok
    '2.000'      -> 2000  (ponto isolado com 3 casas = separador de milhar)
    '2.5' / '2000.50'     -> tratado como decimal
    '2.000.000'  -> 2000000
    """
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    raw = raw.replace("R$", "").replace(" ", "").replace(" ", "")
    neg = raw.startswith("-")
    raw = raw.lstrip("-")

    if "," in raw:
        # virgula = separador decimal; pontos = milhar
        raw = raw.replace(".", "").replace(",", ".")
    elif raw.count(".") > 1:
        # varios pontos so fazem sentido como separador de milhar
        raw = raw.replace(".", "")
    elif raw.count(".") == 1:
        inteiro, dec = raw.split(".")
        # "2.000" (3 casas apos o ponto e parte inteira curta) = milhar
        if len(dec) == 3 and 1 <= len(inteiro) <= 3:
            raw = inteiro + dec
        # senao mantem como decimal ("2000.00", "2.5", "1234.56")

    try:
        d = Decimal(raw).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        return -d if neg else d
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


def format_valor(value: Decimal | float | int | str | None) -> str:
    """Formato BR para preencher inputs de moeda: '2.000,00' (sem 'R$', vazio se nulo)."""
    if value is None or value == "":
        return ""
    return format_brl(value).replace("R$", "").strip()


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


def alerta_agenda(data_carregamento, *, status_agenda: str | None = None) -> str | None:
    """HOJE / AMANHÃ / PRÓXIMO (ate 7 dias) / ATRASADO, ou None se for mais adiante.
    Carregamentos ja concluidos/cancelados nao geram alerta de atraso."""
    from app.constants import AGENDA_CANCELADO, AGENDA_CARREGADO
    from app.constants import ALERTA_AMANHA, ALERTA_ATRASADO, ALERTA_HOJE, ALERTA_PROXIMO

    if data_carregamento is None:
        return None
    dias = (data_carregamento - utcnow().date()).days
    if status_agenda in (AGENDA_CARREGADO, AGENDA_CANCELADO):
        return None
    if dias < 0:
        return ALERTA_ATRASADO
    if dias == 0:
        return ALERTA_HOJE
    if dias == 1:
        return ALERTA_AMANHA
    if dias <= 7:
        return ALERTA_PROXIMO
    return None


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
