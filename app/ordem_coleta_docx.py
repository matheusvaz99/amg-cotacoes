"""Preenche o modelo .docx real da Ordem de Coleta (AMG Transportes / AMGLOG
/ JVA, conforme a empresa/filial escolhida) com os dados que o sistema tem.

Campos operacionais que so a Logistica sabe depois de despachar (motorista,
placas, ANTT, CT-e, adiantamento/saldo, liberacao Buonny) ficam em branco no
documento, prontos para preenchimento manual -- nao inventamos esses dados.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from docx import Document
from docx.table import _Cell, _Row

from app.filiais import EMPRESA_TEMPLATE
from app.models import Quote
from app.utils import format_brl, format_peso

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "assets" / "ordem_coleta"


def _endereco(cidade: str | None, cep, endereco, bairro) -> str:
    partes = [p for p in [endereco, bairro, cidade, f"CEP {cep}" if cep else None] if p]
    return ", ".join(partes) if partes else "-"


def _first_value_cell(row: _Row) -> _Cell | None:
    """Primeira celula, andando da esquerda, cujo bloco de merge e diferente
    do rotulo (cells[0]). Funciona tanto para linhas de campo unico (o valor
    e um merge unico do resto da linha) quanto para linhas com dois campos
    lado a lado (o valor do 1o campo fica logo apos o rotulo, antes do 2o
    rotulo comecar)."""
    label_tc = row.cells[0]._tc
    for cell in row.cells[1:]:
        if cell._tc is not label_tc:
            return cell
    return None


def _last_value_cell(row: _Row) -> _Cell | None:
    """Ultima celula da linha, se for distinta do rotulo -- usado para o 2o
    campo ("N. DA COTACAO/COLETA") que divide a linha com "COMERCIAL
    RESPONSAVEL"."""
    target = row.cells[-1]
    return target if target._tc is not row.cells[0]._tc else None


def _set_first(row: _Row, texto) -> None:
    target = _first_value_cell(row)
    if target is not None:
        target.text = str(texto) if texto not in (None, "") else "-"


def _set_last(row: _Row, texto) -> None:
    target = _last_value_cell(row)
    if target is not None:
        target.text = str(texto) if texto not in (None, "") else "-"


def build_ordem_coleta_docx(quote: Quote) -> bytes:
    oc = quote.ordem_coleta
    solicitacao = quote.solicitacao
    proposal = quote.proposal
    template_name = EMPRESA_TEMPLATE.get(oc.empresa, "amg_transportes.docx")
    doc = Document(str(TEMPLATES_DIR / template_name))

    numero_cotacao = f"{quote.code} / {oc.numero}"
    campos_simples = {
        "N° DA COTAÇÃO/COLETA:": numero_cotacao,
        "DATA E HORA DA COLETA": quote.data_coleta.strftime("%d/%m/%Y"),
        "DATA E HORA DE ENTREGA": (
            quote.data_entrega.strftime("%d/%m/%Y") if quote.data_entrega else "-"
        ),
        "TIPO DE VEÍCULO": quote.tipo_veiculo or "-",
        "TIPO DO MATERIAL": quote.tipo_material
        + (f" - {quote.descricao_material}" if quote.descricao_material else ""),
        "VOLUME DO MATERIAL": str(quote.qtd_volumes) if quote.qtd_volumes else "-",
        "EMAIL PARA ENVIO BOLETO": quote.client_email,
        "TELEFONE DO SOLICITANTE": quote.client_phone or "-",
        "SOLICITANTE DO FRETE (NOME)": quote.client_name,
        "CNPJ PAGADOR DO FRETE": solicitacao.pagador_documento if solicitacao else "-",
        "FE TOTAL EMPRESA R$:": format_brl(proposal.valor_final) if proposal else "-",
    }

    for table in doc.tables:
        secao: str | None = None
        for row in table.rows:
            label = row.cells[0].text.strip()
            if not label:
                continue

            if label.startswith("ENDEREÇOS"):
                secao = "coleta" if "COLETA" in label else "entrega" if "ENTREGA" in label else None
                continue

            if secao == "coleta" and label == "NOME DA EMPRESA":
                _set_first(row, quote.client_company)
            elif secao == "entrega" and label == "NOME DA EMPRESA":
                _set_first(row, solicitacao.destinatario_nome if solicitacao else "-")
            elif secao == "coleta" and "ENDEREÇO COMPLETO" in label:
                _set_first(row, _endereco(
                    quote.origem_cidade, quote.origem_cep, quote.origem_endereco, quote.origem_bairro
                ))
            elif secao == "entrega" and "ENDEREÇO COMPLETO" in label:
                _set_first(row, _endereco(
                    quote.destino_cidade, quote.destino_cep, quote.destino_endereco, quote.destino_bairro
                ))
            elif secao == "coleta" and label == "CNPJ COLETA":
                _set_first(row, oc.cnpj_filial)
            elif label == "COMERCIAL RESPONSÁVEL":
                # a mesma linha carrega o rotulo "N. DA COTACAO/COLETA" mais
                # a frente, com seu proprio valor no ultimo slot da linha.
                _set_last(row, numero_cotacao)
            elif label == "PESO":
                _set_first(row, f"{format_peso(quote.peso_total_kg)} kg")
            elif label in campos_simples:
                _set_first(row, campos_simples[label])

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()
