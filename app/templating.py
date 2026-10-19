"""Instancia compartilhada do Jinja2Templates com filtros e globais."""

from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.constants import (
    CONDICAO_PAGAMENTO_OPCOES,
    DISCLAIMERS,
    MAX_LOCAIS_POR_TIPO,
    SLOGAN,
    STATUS_LABELS,
    TERMOS_COTACAO,
)
from app.utils import format_brl, para_brasilia, termos_cotacao

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _date_br(d):
    d = para_brasilia(d)
    return d.strftime("%d/%m/%Y") if d else "-"


def _datetime_br(d):
    d = para_brasilia(d)
    return d.strftime("%d/%m/%Y %H:%M") if d else "-"


templates.env.filters["brl"] = format_brl
templates.env.filters["date_br"] = _date_br
templates.env.filters["datetime_br"] = _datetime_br
templates.env.globals["STATUS_LABELS"] = STATUS_LABELS
templates.env.globals["DISCLAIMERS"] = DISCLAIMERS
templates.env.globals["SLOGAN"] = SLOGAN
templates.env.globals["TERMOS_COTACAO"] = TERMOS_COTACAO
templates.env.globals["MAX_LOCAIS_POR_TIPO"] = MAX_LOCAIS_POR_TIPO
templates.env.globals["CONDICAO_PAGAMENTO_OPCOES"] = CONDICAO_PAGAMENTO_OPCOES
templates.env.globals["termos_cotacao"] = termos_cotacao


def render(request, name: str, **ctx):
    return templates.TemplateResponse(request, name, ctx)
