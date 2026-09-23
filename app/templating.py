"""Instancia compartilhada do Jinja2Templates com filtros e globais."""

from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.constants import DISCLAIMERS, SLOGAN, STATUS_LABELS, TERMOS_COTACAO
from app.utils import format_brl

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

templates.env.filters["brl"] = format_brl
templates.env.filters["date_br"] = lambda d: d.strftime("%d/%m/%Y") if d else "-"
templates.env.globals["STATUS_LABELS"] = STATUS_LABELS
templates.env.globals["DISCLAIMERS"] = DISCLAIMERS
templates.env.globals["SLOGAN"] = SLOGAN
templates.env.globals["TERMOS_COTACAO"] = TERMOS_COTACAO


def render(request, name: str, **ctx):
    return templates.TemplateResponse(request, name, ctx)
