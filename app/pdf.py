"""Geracao do PDF da cotacao com a identidade visual da AMG Logistica.

Usa fpdf2 (Python puro, sem dependencias de sistema). As fontes nucleo do
PDF sao latin-1, entao todo texto dinamico passa por `_s()`.
"""

from __future__ import annotations

from datetime import datetime

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from app.constants import DISCLAIMERS, SLOGAN, STATUS_LABELS
from app.models import Quote
from app.utils import format_brl, format_peso

NAVY = (11, 33, 56)
ORANGE = (242, 106, 33)
INK = (31, 42, 55)
MUTED = (91, 100, 114)
LINE = (226, 230, 236)
LIGHT = (241, 244, 248)

_REPL = {
    "→": ">", "←": "<", "—": "-", "–": "-",
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "…": "...", " ": " ", "•": "-",
}


def _s(text) -> str:
    if text is None:
        return "-"
    text = str(text)
    for bad, good in _REPL.items():
        text = text.replace(bad, good)
    return text.encode("latin-1", "replace").decode("latin-1")


def _local(cidade: str, cep, endereco, bairro) -> str:
    partes = [cidade]
    if cep:
        partes.append(f"CEP {cep}")
    if endereco:
        partes.append(endereco)
    if bairro:
        partes.append(bairro)
    return " - ".join(partes)


class QuotePDF(FPDF):
    def __init__(self, quote: Quote):
        super().__init__(format="A4")
        self.quote = quote
        self.set_title(f"Cotacao {quote.code} - AMG Logistica")
        self.set_author("AMG Logistica")
        self.set_auto_page_break(auto=True, margin=24)
        self.set_margins(16, 34, 16)

    # -- cabecalho e rodape em toda pagina --------------------------------
    def header(self):
        self.set_fill_color(*NAVY)
        self.rect(0, 0, self.w, 26, style="F")
        self.set_fill_color(*ORANGE)
        self.rect(0, 26, self.w, 1.2, style="F")

        self.set_xy(16, 6.5)
        self.set_font("Helvetica", "B", 20)
        self.set_text_color(*ORANGE)
        self.cell(24, 8, "AMG")
        self.set_xy(16, 15)
        self.set_font("Helvetica", "B", 7)
        self.set_text_color(255, 255, 255)
        self.cell(40, 4, "L O G I S T I C A")

        self.set_xy(self.w - 96, 7)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(255, 255, 255)
        self.cell(80, 6, "COTACAO DE FRETE", align="R")
        self.set_xy(self.w - 96, 15)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(206, 214, 224)
        self.cell(80, 5, _s(self.quote.code), align="R")

        self.set_y(34)

    def footer(self):
        self.set_y(-21)
        self.set_draw_color(*ORANGE)
        self.set_line_width(0.5)
        self.line(16, self.get_y(), self.w - 16, self.get_y())
        self.ln(2)
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*NAVY)
        self.cell(0, 4, _s(SLOGAN), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("Helvetica", "", 6.5)
        self.set_text_color(*MUTED)
        gerado = datetime.now().strftime("%d/%m/%Y %H:%M")
        self.cell(
            0, 3.6,
            _s(f"AMG Logistica  -  documento gerado em {gerado}  -  pagina {self.page_no()}"),
            align="C",
        )

    # -- blocos reutilizaveis -------------------------------------------
    def section(self, titulo: str):
        if self.get_y() > self.h - 45:
            self.add_page()
        self.ln(3.5)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*ORANGE)
        self.cell(0, 6, _s(titulo.upper()), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*LINE)
        self.set_line_width(0.3)
        self.line(16, self.get_y(), self.w - 16, self.get_y())
        self.ln(1.5)

    def row(self, label: str, value):
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*MUTED)
        self.cell(46, 5.6, _s(label))
        self.set_text_color(*INK)
        self.set_font("Helvetica", "B", 9)
        self.multi_cell(0, 5.6, _s(value), new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _items(pdf: QuotePDF, proposal) -> None:
    pdf.set_draw_color(*LINE)
    pdf.set_line_width(0.3)
    for label, valor in (
        ("Frete", proposal.frete),
        ("Pedagio", proposal.pedagio),
        ("Seguro (0,2%)", proposal.seguro),
    ):
        pdf.set_font("Helvetica", "", 9.5)
        pdf.set_text_color(*INK)
        pdf.cell(120, 7, _s(label), border="B")
        pdf.cell(0, 7, _s(format_brl(valor)), border="B", align="R",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(1)
    pdf.set_fill_color(*LIGHT)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*NAVY)
    pdf.cell(120, 9, "  TOTAL", fill=True)
    pdf.cell(0, 9, _s(format_brl(proposal.total)) + "  ", align="R", fill=True,
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def build_quote_pdf(quote: Quote) -> bytes:
    """Monta o PDF da cotacao e devolve os bytes."""
    pdf = QuotePDF(quote)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 8, _s(f"Cotacao {quote.code}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*MUTED)
    status = STATUS_LABELS.get(quote.status, quote.status)
    pdf.cell(
        0, 5,
        _s(f"Status: {status}    |    Solicitada em {quote.created_at.strftime('%d/%m/%Y')}"),
        new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )

    pdf.section("Cliente")
    pdf.row("Nome / empresa", quote.client_name)
    pdf.row("E-mail", quote.client_email)
    pdf.row("Telefone", quote.client_phone or "-")

    pdf.section("Rota")
    pdf.row("Origem (coleta)", _local(
        quote.origem_cidade, quote.origem_cep, quote.origem_endereco, quote.origem_bairro))
    pdf.row("Destino (entrega)", _local(
        quote.destino_cidade, quote.destino_cep, quote.destino_endereco, quote.destino_bairro))

    pdf.section("Carga")
    pdf.row("Tipo de material", quote.tipo_material)
    if quote.descricao_material:
        pdf.row("Descricao", quote.descricao_material)
    pdf.row("Quantidade de volumes", str(quote.qtd_volumes))
    pdf.row("Peso total aproximado", f"{format_peso(quote.peso_total_kg)} kg")
    pdf.row("Valor aproximado da NF", format_brl(quote.valor_nf))
    pdf.row("Servico de carga", "Sim" if quote.servico_carga else "Nao")
    pdf.row("Servico de descarga", "Sim" if quote.servico_descarga else "Nao")

    pdf.section("Transporte")
    pdf.row("Tipo de veiculo desejado", quote.tipo_veiculo)
    pdf.row("Carroceria", quote.carroceria or "-")
    pdf.row("Capacidade aproximada", quote.capacidade_aprox)
    pdf.row("Data prevista para coleta", quote.data_coleta.strftime("%d/%m/%Y"))
    if quote.observacoes:
        pdf.row("Observacoes", quote.observacoes)

    pdf.section("Proposta")
    proposal = quote.proposal
    if proposal is None:
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(*MUTED)
        pdf.multi_cell(0, 5.6, _s("Proposta ainda nao cadastrada para esta cotacao."),
                       new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    else:
        _items(pdf, proposal)
        pdf.ln(2.5)
        pdf.row("Prazo de entrega", proposal.prazo_entrega)
        pdf.row("Validade da proposta", proposal.validade.strftime("%d/%m/%Y"))
        pdf.row("Observacoes", proposal.observacoes or "-")

    pdf.ln(4)
    pdf.set_draw_color(*LINE)
    pdf.line(16, pdf.get_y(), pdf.w - 16, pdf.get_y())
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(*MUTED)
    for item in DISCLAIMERS:
        pdf.multi_cell(0, 4, _s(f"- {item}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return bytes(pdf.output())
