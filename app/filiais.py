"""Empresas do grupo AMG e suas filiais (CNPJ por UF), usadas para emitir a
Ordem de Coleta com o modelo .docx e o CNPJ corretos. Fonte: planilha
`cnpj-filiais.xlsx` fornecida pelo cliente."""

from __future__ import annotations

# Ordem = prioridade de sugestao quando mais de uma empresa tem filial na
# mesma UF (o admin sempre pode escolher outra opcao no dropdown).
FILIAIS_CNPJ: dict[str, dict[str, str]] = {
    "AMG Logistica Ltda": {
        "PR": "53.805.774/0001-56", "SP": "53.805.774/0002-37",
        "RJ": "53.805.774/0003-18", "ES": "53.805.774/0004-07",
    },
    "AMG Logistica e Transportes Eireli": {
        "PR": "09.913.149/0001-36", "SP": "09.913.149/0002-17",
        "RJ": "09.913.149/0003-06",
    },
    "JVA Logistica e Transportes Ltda": {
        "PR": "22.729.681/0001-66", "BA": "22.729.681/0002-47",
        "SP": "22.729.681/0003-28", "RS": "22.729.681/0004-09",
        "SC": "22.729.681/0005-90", "MG": "22.729.681/0006-70",
    },
    "AMG Expresso Ltda": {
        "SP": "50.786.286/0001-50", "PR": "50.786.286/0002-31",
        "MS": "50.786.286/0003-12", "DF": "50.786.286/0005-84",
    },
}

# Qual modelo .docx (em assets/ordem_coleta/) cada empresa usa. AMG Logistica
# e Transportes Eireli e AMG Expresso Ltda compartilham o mesmo modelo/marca
# "AMG Transportes" (so ha 3 modelos para as 4 empresas).
EMPRESA_TEMPLATE: dict[str, str] = {
    "AMG Logistica Ltda": "amglog.docx",
    "AMG Logistica e Transportes Eireli": "amg_transportes.docx",
    "JVA Logistica e Transportes Ltda": "jva.docx",
    "AMG Expresso Ltda": "amg_transportes.docx",
}

EMPRESAS_OC = list(FILIAIS_CNPJ.keys())


def extrair_uf(cidade_uf: str | None) -> str | None:
    """'Curitiba - PR' -> 'PR'. Devolve None se nao conseguir extrair."""
    if not cidade_uf or "-" not in cidade_uf:
        return None
    uf = cidade_uf.rsplit("-", 1)[-1].strip().upper()
    return uf if len(uf) == 2 and uf.isalpha() else None


def opcoes_empresa_cnpj() -> list[tuple[str, str]]:
    """(value, label) de cada filial cadastrada, para popular o dropdown.
    value = 'Empresa|CNPJ' (chave estavel para reconstruir a escolha)."""
    itens = []
    for empresa, ufs in FILIAIS_CNPJ.items():
        for uf, cnpj in ufs.items():
            itens.append((f"{empresa}|{cnpj}", f"{empresa} — {uf} — {cnpj}"))
    return itens


def sugestao_empresa_cnpj(uf: str | None) -> str | None:
    """Value pre-selecionado: primeira empresa (por prioridade) com filial
    na UF informada. None se nenhuma tiver (admin escolhe manualmente)."""
    if not uf:
        return None
    for empresa, ufs in FILIAIS_CNPJ.items():
        if uf in ufs:
            return f"{empresa}|{ufs[uf]}"
    return None


def parse_empresa_cnpj(value: str | None) -> tuple[str, str] | None:
    """'Empresa|CNPJ' -> (empresa, cnpj), validando que a empresa existe."""
    if not value or "|" not in value:
        return None
    empresa, cnpj = value.split("|", 1)
    if empresa not in FILIAIS_CNPJ:
        return None
    return empresa, cnpj
